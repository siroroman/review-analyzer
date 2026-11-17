from collections.abc import Sequence

from app.domain import RawReview, Review
from app.sanitize._text import clean_text, text_hash
from app.sanitize._types import InjectionDetector, PreparedReviews


def _is_flagged(detector: InjectionDetector, text: str) -> bool:
    try:
        return detector.is_injection(text)
    except Exception:
        return True  # fail closed: a Review nobody could check is not analysed


def prepare(raw: Sequence[RawReview], detector: InjectionDetector) -> PreparedReviews:
    """Turn Raw Reviews into clean and Flagged reviews: no HTML, hidden characters or contacts, no repeats."""
    clean: list[Review] = []
    flagged: list[Review] = []
    textless: list[Review] = []
    seen_ids: set[tuple[str, str]] = set()
    seen_texts: set[tuple[str, str, str, int, object]] = set()
    duplicates = 0
    for item in raw:
        id_key = (item.source, item.external_id)  # storage is UNIQUE on exactly this pair
        if id_key in seen_ids:
            duplicates += 1
            continue
        seen_ids.add(id_key)
        text = clean_text(item.text)
        digest = text_hash(text)
        if not text:
            # A star-only rating: it has no text to compare, so only its id can make it a duplicate.
            textless.append(_review(item, text, digest, flagged=False))
            continue
        text_key = (item.source, item.place_external_id, digest, item.rating, item.published_on)
        if text_key in seen_texts:
            duplicates += 1
            continue
        seen_texts.add(text_key)
        is_flagged = _is_flagged(detector, text)
        (flagged if is_flagged else clean).append(_review(item, text, digest, flagged=is_flagged))
    return PreparedReviews(clean=clean, flagged=flagged, textless=textless, duplicates=duplicates)


def _review(item: RawReview, text: str, digest: str, *, flagged: bool) -> Review:
    return Review(
        source=item.source,
        place_external_id=item.place_external_id,
        external_id=item.external_id,
        rating=item.rating,
        text=text,
        published_on=item.published_on,
        date_precision=item.date_precision,
        language=item.language,
        text_hash=digest,
        flagged=flagged,
    )
