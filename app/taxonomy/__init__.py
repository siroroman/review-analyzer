"""Taxonomy: the frozen list of Topics of an industry, generated once from a sample of Reviews."""

from app.taxonomy._taxonomy import (
    GENERIC_INDUSTRY,
    MAX_INDUSTRY_LENGTH,
    MAX_SAMPLE,
    MAX_TOPICS,
    MIN_SAMPLE,
    MIN_TOPICS,
    UNCLASSIFIED_KEY,
    InvalidIndustry,
    InvalidTaxonomy,
    SampleTooSmall,
    Taxonomies,
    TaxonomyError,
)

__all__ = [
    "GENERIC_INDUSTRY",
    "MAX_INDUSTRY_LENGTH",
    "MAX_SAMPLE",
    "MAX_TOPICS",
    "MIN_SAMPLE",
    "MIN_TOPICS",
    "UNCLASSIFIED_KEY",
    "InvalidIndustry",
    "InvalidTaxonomy",
    "SampleTooSmall",
    "Taxonomies",
    "TaxonomyError",
]
