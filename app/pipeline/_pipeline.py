from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal
from functools import partial
from typing import Protocol

from app.classification import ClassificationResult
from app.domain import (
    Company,
    Metrics,
    Place,
    RawReview,
    Review,
    ReviewTopic,
    RunStatus,
    Source,
    Topic,
)
from app.gateway import BudgetExceeded, ClientError, GatewayDenied
from app.insights import Insights
from app.llm import LlmError, Sleeper
from app.metrics import compute
from app.pipeline._types import NOTE_INDUSTRY_FALLBACK, PipelineConfig, RunReport, RunResult
from app.sanitize import InjectionDetector, prepare
from app.storage import CallFilter, RunRecord, Storage, StoredTaxonomy, UnknownRun
from app.taxonomy import GENERIC_INDUSTRY, UNCLASSIFIED_KEY, TaxonomyError

_RANK = {
    RunStatus.QUEUED: 0,
    RunStatus.DOWNLOADING: 1,
    RunStatus.CLASSIFYING: 2,
    RunStatus.ANALYZING: 3,
}
_FINAL = (RunStatus.DONE, RunStatus.PARTIAL, RunStatus.FAILED)
# A step failing like this ends the Run with what is finished. Anything else is a bug and propagates,
# leaving the Run at its status so the queue's redelivery resumes it.
_STEP_FAILURES = (BudgetExceeded, GatewayDenied, ClientError, LlmError, TaxonomyError)


class SourceFetcher(Protocol):
    """The part of `sources.Sources` that `pipeline` uses."""

    def fetch_reviews(
        self, place: Place, since: date | None, limit: int, *, run_id: str
    ) -> list[RawReview]: ...


class TaxonomyProvider(Protocol):
    """The part of `taxonomy.Taxonomies` that `pipeline` uses."""

    def infer_industry(self, *, sample: Callable[[], Sequence[Review]], run_id: str) -> str: ...

    def get_taxonomy(
        self, industry: str, *, sample: Callable[[], Sequence[Review]], run_id: str
    ) -> StoredTaxonomy: ...


class ReviewClassifier(Protocol):
    """The part of `classification.Classifier` that `pipeline` uses."""

    def classify(
        self, source: Source, place_external_id: str, taxonomy: StoredTaxonomy, *, run_id: str
    ) -> ClassificationResult: ...


class InsightMaker(Protocol):
    """The part of `insights.InsightGenerator` that `pipeline` uses."""

    def generate(self, metrics: Metrics, samples: Sequence[Review], *, run_id: str) -> Insights: ...


class Pipeline:
    """Runs a Run: download, sanitize, industry, Taxonomy, classify, Metrics, Insights.

    Every step is idempotent and the status only moves forward, so a redelivered or crashed Run resumes
    where it stopped and a finished one is left alone.
    """

    def __init__(
        self,
        *,
        storage: Storage,
        sources: SourceFetcher,
        detector: InjectionDetector,
        taxonomies: TaxonomyProvider,
        classifier: ReviewClassifier,
        insights: InsightMaker,
        sleeper: Sleeper,
        config: PipelineConfig,
    ) -> None:
        self._storage = storage
        self._sources = sources
        self._detector = detector
        self._taxonomies = taxonomies
        self._classifier = classifier
        self._insights = insights
        self._sleeper = sleeper
        self._config = config

    def run(self, run_id: str) -> RunResult:
        """Run it to the end and return the result: `done`, `partial` (Budget exceeded or a step failed
        past retry; what was finished is kept) or `failed` (a step failed and no Review exists).

        A finished Run returns its stored result. A queued Run of a Company with a fresh `done` Run copies
        that result and calls nothing. Raises `UnknownRun`; a bug propagates and leaves the Run resumable.
        """
        record = self._storage.runs.get(run_id)
        if record is None:
            raise UnknownRun(run_id)
        company = self._company(record)
        if record.status in _FINAL:
            return self._result(record, company)
        if record.status is RunStatus.QUEUED and self._reuse_fresh(record):
            done = self._advance(record.id, RunStatus.DONE)
            return self._result(done, self._company(done))
        failure = self._steps(record, company)
        known = self._company(record)  # the industry may have been inferred meanwhile
        if failure is None:
            return self._result(self._advance(run_id, RunStatus.DONE), known)
        self._save_trend(run_id, self._metrics(known))
        empty = not self._reviews(known) and not isinstance(failure, BudgetExceeded)
        end = RunStatus.FAILED if empty else RunStatus.PARTIAL
        return self._result(self._advance(run_id, end), known)

    def _company(self, record: RunRecord) -> Company:
        """The stored Company, with the industry this Run used; a Run before that was recorded has the
        Company's own."""
        stored = self._storage.companies.by_id(record.company_id)
        fresh = self._storage.runs.get(record.id)
        if stored is None or fresh is None:
            raise RuntimeError(f"Run {record.id} has no stored Company")
        if fresh.industry is None:
            return stored.company
        return stored.company.model_copy(update={"industry": fresh.industry})

    def report(self, run_id: str) -> RunReport:
        """What the dashboard shows of a Run, for any status. Raises `UnknownRun`."""
        record = self._storage.runs.get(run_id)
        if record is None:
            raise UnknownRun(run_id)
        company = self._company(record)
        # The trend and the changes of today's Reviews could contradict the Run's Insights, so a report
        # carries the ones the Run saved.
        saved = {
            "trend": tuple(self._storage.trends.for_run(run_id)),
            "changes": tuple(self._storage.changes.for_run(run_id)),
        }
        metrics = self._metrics(company).model_copy(update=saved)
        return RunReport(
            result=self._result(record, company),
            company=company,
            metrics=metrics,
            insights=tuple(self._storage.insights.for_run(run_id)),
            topics=self._mentioned_topics(company, metrics),
        )

    def _mentioned_topics(self, company: Company, metrics: Metrics) -> tuple[Topic, ...]:
        taxonomy = self._latest_taxonomy(company)
        if taxonomy is None:
            return ()
        mentioned = {share.topic_key for share in metrics.topic_shares}
        mentioned |= {c.main_topic_key for c in metrics.changes if c.main_topic_key}
        return tuple(topic for topic in taxonomy.taxonomy.topics if topic.key in mentioned)

    def _latest_taxonomy(self, company: Company) -> StoredTaxonomy | None:
        return None if company.industry is None else self._storage.taxonomies.latest(company.industry)

    def _steps(self, record: RunRecord, company: Company) -> Exception | None:
        run_id = record.id
        status = record.status
        try:
            if _RANK[status] <= _RANK[RunStatus.DOWNLOADING]:
                status = self._enter(run_id, status, RunStatus.DOWNLOADING)
                self._download(run_id, company)
            if _RANK[status] <= _RANK[RunStatus.CLASSIFYING]:
                status = self._enter(run_id, status, RunStatus.CLASSIFYING)
                self._classify(record, company)
            status = self._enter(run_id, status, RunStatus.ANALYZING)
            self._analyze(run_id, self._company(record))
        except _STEP_FAILURES as failure:
            return failure
        return None

    def _enter(self, run_id: str, status: RunStatus, target: RunStatus) -> RunStatus:
        return status if status is target else self._advance(run_id, target).status

    def _advance(self, run_id: str, status: RunStatus) -> RunRecord:
        return self._storage.runs.advance(run_id, status)

    def _reuse_fresh(self, record: RunRecord) -> bool:
        """Give a queued Run the result of the Company's fresh `done` Run, all at once.

        The copy is one storage step and a repeat is harmless, so a crash before the Run is `done` leaves
        either nothing or the whole result. A queued Run that already holds one (an earlier attempt copied
        it) is finished as it is, however old its source has become.
        """
        if self._holds_result(record.id):
            return True
        fresh = self._storage.runs.fresh_for(record.company_id, self._config.cache_ttl)
        if fresh is None:
            return False
        self._storage.runs.copy_results(fresh.id, record.id)
        return True

    def _holds_result(self, run_id: str) -> bool:
        # Steps write only after they entered their status, so a queued Run can hold rows only as a copy.
        return bool(self._storage.insights.for_run(run_id) or self._storage.trends.for_run(run_id))

    def _attempt[T](self, step: Callable[[], T]) -> T:
        """Run `step`; repeat it after a transient provider failure, up to `max_attempts` times."""
        attempt = 1
        while True:
            try:
                return step()
            except ClientError as error:
                if error.kind not in self._config.retryable_kinds or attempt >= self._config.max_attempts:
                    raise
                self._sleeper.sleep(self._config.retry_delay * 2 ** (attempt - 1))
                attempt += 1

    def _places(self, company: Company) -> list[Place]:
        return [p for p in company.places if p.source in self._config.sources]

    def _reviews(self, company: Company) -> list[Review]:
        found: list[Review] = []
        for place in self._places(company):
            found += self._storage.reviews.list_for_place(place.source, place.external_id)
        return found

    def _download(self, run_id: str, company: Company) -> None:
        for place in self._places(company):
            stored = self._storage.reviews.list_for_place(place.source, place.external_id)
            since = max((r.published_on for r in stored), default=None)
            fetch = partial(
                self._sources.fetch_reviews, place, since, self._config.reviews_per_place, run_id=run_id
            )
            raw = self._attempt(fetch)
            prepared = prepare(raw, self._detector)
            self._storage.reviews.add([*prepared.clean, *prepared.flagged])

    def _industry(self, record: RunRecord, company: Company) -> str:
        """The Company's industry; inferred from the downloaded Reviews while it is unknown or generic.

        When the model fails, answers invalidly or too few Reviews exist, the Run goes on with the generic
        industry and says so in its notes. An exceeded Budget or a denied call still ends the Run.
        """
        if company.industry not in (None, GENERIC_INDUSTRY):
            return str(company.industry)
        try:
            industry = self._attempt(
                lambda: self._taxonomies.infer_industry(
                    sample=lambda: self._reviews(company), run_id=record.id
                )
            )
        except (ClientError, LlmError, TaxonomyError):
            industry = GENERIC_INDUSTRY
        if industry != company.industry:
            self._storage.companies.set_industry(record.company_id, industry)
        return industry

    def _classify(self, record: RunRecord, company: Company) -> None:
        run_id = record.id
        industry = self._industry(record, company)
        self._storage.runs.set_industry(run_id, industry)
        taxonomy = self._attempt(
            lambda: self._taxonomies.get_taxonomy(
                industry, sample=lambda: self._reviews(company), run_id=run_id
            )
        )
        for place in self._places(company):
            self._attempt(
                partial(self._classifier.classify, place.source, place.external_id, taxonomy, run_id=run_id)
            )

    def _topics(self, company: Company) -> list[ReviewTopic]:
        taxonomy = self._latest_taxonomy(company)
        if taxonomy is None:
            return []
        found: list[ReviewTopic] = []
        for place in self._places(company):
            found += self._storage.reviews.topics_for_place(place.source, place.external_id, taxonomy)
        return found

    def _metrics(self, company: Company) -> Metrics:
        return compute(self._reviews(company), self._topics(company))

    def _save_trend(self, run_id: str, metrics: Metrics) -> None:
        if metrics.trend and not self._storage.trends.for_run(run_id):
            self._storage.trends.save(run_id, metrics.trend)
        if metrics.changes and not self._storage.changes.for_run(run_id):
            self._storage.changes.save(run_id, metrics.changes)

    def _analyze(self, run_id: str, company: Company) -> None:
        metrics = self._metrics(company)
        self._save_trend(run_id, metrics)
        if self._storage.insights.for_run(run_id):
            return
        newest_first = sorted(self._reviews(company), key=lambda r: r.published_on, reverse=True)
        made = self._attempt(lambda: self._insights.generate(metrics, newest_first, run_id=run_id))
        if made.insights:
            self._storage.insights.save(run_id, made.insights)

    def _result(self, record: RunRecord, company: Company) -> RunResult:
        reviews = self._reviews(company)
        real = {t.review_external_id for t in self._topics(company) if t.topic_key != UNCLASSIFIED_KEY}
        spent = self._storage.calls.cost_by_run(CallFilter(run_id=record.id))
        return RunResult(
            run_id=record.id,
            status=record.status,
            reviews=len(reviews),
            flagged=sum(r.flagged for r in reviews),
            unclassified=sum(1 for r in reviews if not r.flagged and r.external_id not in real),
            insights=len(self._storage.insights.for_run(record.id)),
            trend_points=len(self._storage.trends.for_run(record.id)),
            cost=spent.get(record.id, Decimal(0)),
            notes=(NOTE_INDUSTRY_FALLBACK,) if company.industry == GENERIC_INDUSTRY else (),
        )
