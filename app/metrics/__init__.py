"""Numbers and trends: pure functions, no I/O (ADR-0004)."""

from app.metrics._average import average_rating
from app.metrics._compute import CHANGE_THRESHOLD, MIN_REVIEWS_PER_PERIOD, compute

__all__ = ["CHANGE_THRESHOLD", "MIN_REVIEWS_PER_PERIOD", "average_rating", "compute"]
