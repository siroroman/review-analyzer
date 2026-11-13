import re
from collections.abc import Collection
from datetime import date

from app.domain import Change, ChangeKind, Insight, Metrics
from app.insights._prompt import ModelInsight

_PERSONAL_DATA = re.compile(
    r"[\w.+-]+@[\w-]+\.[\w.-]+"  # email
    r"|https?://\S+|\bwww\.\S+"  # link
    r"|(?:\+?\d[\s.-]?){9,}"  # phone number or long account number
    r"|\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,}\b",  # IBAN
    re.IGNORECASE,
)
_INSULT = re.compile(
    r"\b(?:idiot\w*|moron\w*|imbecil\w*|debil\w*|blb(?:ec|ci|ce)\b|kret[eé]n\w*|čurák\w*|"
    r"dement\w*|retard\w*|v[ůu]l\b|vole\b|vol[ůu]\w*|hovad\w*|hovn\w*|kokot\w*|zmrd\w*|"
    r"p[ií]č\w*|kr[aá]v(?:a|y|u|o|ě|e|ám|ách|ami)\b|pr[aá]sa\w*|prase\b|svin\w*|zm[ií]t\w*|debil\w*)",
    re.IGNORECASE,
)


def ground(items: list[ModelInsight], shown_ids: Collection[str]) -> tuple[list[Insight], int]:
    """Keep the Insights whose every Review ID was shown to the model. Returns them and the dropped count."""
    kept: list[Insight] = []
    for item in items:
        if not item.review_ids or not set(item.review_ids) <= set(shown_ids):
            continue
        try:
            kept.append(
                Insight(
                    type=item.type,
                    period_start=date.fromisoformat(item.period_start),
                    period_end=date.fromisoformat(item.period_end),
                    text=item.text,
                    review_ids=tuple(item.review_ids),
                )
            )
        except ValueError:  # bad date, empty text, period out of order
            continue
    return kept, len(items) - len(kept)


def content_check(insights: list[Insight]) -> tuple[list[Insight], int]:
    """Remove Insights that hold personal data or insults. Returns the rest and the removed count."""
    kept = [i for i in insights if not (_PERSONAL_DATA.search(i.text) or _INSULT.search(i.text))]
    return kept, len(insights) - len(kept)


def fallback_summary(metrics: Metrics) -> str:
    """A deterministic summary from Metrics alone, for when no Insight survives."""
    if metrics.overall is None:
        return "No reviews to summarise."
    head = f"Average rating {metrics.overall.average_rating:.1f} from {metrics.overall.count} reviews."
    drops = [c for c in metrics.changes if c.kind is ChangeKind.DROP]
    rises = [c for c in metrics.changes if c.kind is ChangeKind.RISE]
    if not metrics.changes:
        return f"{head} No drops or rises detected."
    counts = f"{_plural(len(drops), 'drop')} and {_plural(len(rises), 'rise')} detected"
    biggest = max(metrics.changes, key=lambda c: abs(c.delta))
    return f"{head} {counts}; the biggest change is {_describe(biggest)}."


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _describe(change: Change) -> str:
    topic = f" ({change.main_topic_key})" if change.main_topic_key else ""
    return f"{change.delta:+.1f} stars on {change.source.value} in {change.period_start:%Y-%m}{topic}"
