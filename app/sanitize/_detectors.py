import re

_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(?:ignore|disregard|forget|override)\b.{0,30}\b(?:previous|prior|above|earlier|all|your)\b.{0,30}"
        r"\b(?:instructions?|prompts?|rules?|context)\b",
        r"\bdisregard (?:the )?above\b",
        r"\byou are now\b",
        r"\b(?:reveal|show|print|repeat)\b.{0,20}\b(?:system prompt|api key|secret|instructions)\b",
        r"(?:^|\s)(?:system|assistant)\s*:",
        r"\bnew instructions?\s*:",
        r"</?\s*(?:review|reviews|system|instructions?)\b",
        r"\b(?:ignoruj|ignorujte|zapomeň|zapomeňte)\b.{0,30}\b(?:předchozí|předešlé|všechny|své)\b.{0,30}"
        r"\b(?:instrukce|pokyny|pravidla)\b",
    )
]


class PatternInjectionDetector:
    """A rule-based InjectionDetector for the common English and Czech phrasings; it never raises."""

    def is_injection(self, text: str) -> bool:
        return any(p.search(text) for p in _PATTERNS)
