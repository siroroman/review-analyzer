"""Run classification over the set and turn the answers into a report."""

from datetime import date

from app.classification import Classifier
from app.domain import Clock, Company, DatePrecision, Place, Review, Source
from app.llm import Llm
from app.storage import in_memory_storage
from evaluation._data import EvaluationSet
from evaluation._report import Report, build_report
from evaluation._score import score

_PLACE = "evaluation"
_PUBLISHED = date(2026, 1, 1)  # a fixed date: the Reviews of the set are not dated


def run_evaluation(llm: Llm, loaded: EvaluationSet, clock: Clock, *, models: str) -> Report:
    """Classify every Review of the set with the real `Classifier` (in-memory storage) and score it.

    The texts reach the model only through `Classifier`, between its data delimiters.
    """
    storage = in_memory_storage(clock)
    storage.companies.get_or_create(
        Company(
            name="Evaluation",
            industry=loaded.taxonomy.industry,
            places=(Place(source=Source.GOOGLE_MAPS, external_id=_PLACE, name="Evaluation", address=""),),
        )
    )
    storage.reviews.add(
        [
            Review(
                source=Source.GOOGLE_MAPS,
                place_external_id=_PLACE,
                external_id=item.id,
                rating=item.rating or 3,
                text=item.text,
                published_on=_PUBLISHED,
                date_precision=DatePrecision.DAY,
                language=item.language,
                text_hash=item.id,
                flagged=False,
            )
            for item in loaded.items
        ]
    )
    stored = storage.taxonomies.save(loaded.taxonomy)
    Classifier(llm, storage.reviews).classify(Source.GOOGLE_MAPS, _PLACE, stored, run_id="evaluation")
    actual = storage.reviews.topics_for_place(Source.GOOGLE_MAPS, _PLACE, stored)
    return build_report(
        score(loaded.items, actual), taxonomy_version=stored.version, taken_at=clock.now(), models=models
    )
