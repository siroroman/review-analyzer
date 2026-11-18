"""Classification: Reviews get Topics, sentiment and confidence.

The `Categorizer` (DeepSeek, one call for all Reviews, ADR-0010) is the product path; the `Classifier`
(Jev, one call per Review) stays as the path used when no `Categorizer` is wired.
"""

from app.classification._categorize import (
    MAX_CATEGORIES,
    MAX_REVIEWS,
    CategorizationResult,
    Categorizer,
)
from app.classification._classification import (
    MAX_TOPICS_PER_REVIEW,
    MIN_SCORE,
    TASK,
    ClassificationResult,
    Classifier,
)

__all__ = [
    "MAX_CATEGORIES",
    "MAX_REVIEWS",
    "CategorizationResult",
    "Categorizer",
    "MAX_TOPICS_PER_REVIEW",
    "MIN_SCORE",
    "TASK",
    "ClassificationResult",
    "Classifier",
]
