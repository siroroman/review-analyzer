from dataclasses import dataclass
from decimal import Decimal

# USD per million tokens, (input, output), by (service, model).
# PLACEHOLDERS: not verified against the providers' price pages. Check before the first paid Run.
_TOKEN_PRICES: dict[tuple[str, str], tuple[Decimal, Decimal]] = {
    ("openrouter", "jev-1.14"): (Decimal("0.10"), Decimal("0.30")),
    ("anthropic", "claude-haiku"): (Decimal(1), Decimal(5)),
    ("anthropic", "claude-sonnet"): (Decimal(3), Decimal(15)),
}

# USD per unit, by (service, unit). PLACEHOLDERS, as above.
_UNIT_PRICES: dict[tuple[str, str], Decimal] = {
    ("apify", "review"): Decimal("0.0006"),
    ("apify", "firmy_item"): Decimal("0.001"),
    ("google_places", "autocomplete_request"): Decimal("0.00283"),
    ("google_places", "details_request"): Decimal("0.017"),
    ("google_places", "text_search_request"): Decimal("0.032"),
}

_MILLION = Decimal(1_000_000)


class UnknownPrice(LookupError):
    """A paid service, model or unit has no price: the call must not run unpriced."""


def _non_negative(**values: int) -> None:
    for name, value in values.items():
        if value < 0:
            raise ValueError(f"{name} must not be negative")


@dataclass(frozen=True)
class Tokens:
    """Model usage: tokens in and out."""

    service: str
    model: str
    input: int
    output: int

    def __post_init__(self) -> None:
        _non_negative(input=self.input, output=self.output)


@dataclass(frozen=True)
class Units:
    """Usage of a per-unit service: items scraped, Places requests."""

    service: str
    unit: str
    count: int

    def __post_init__(self) -> None:
        _non_negative(count=self.count)


def estimate_cost(usage: Tokens | Units) -> Decimal:
    """Price of the usage in USD from the price table."""
    if isinstance(usage, Tokens):
        key = (usage.service, usage.model)
        if key not in _TOKEN_PRICES:
            raise UnknownPrice(f"no token price for {usage.service}/{usage.model}")
        price_in, price_out = _TOKEN_PRICES[key]
        return (price_in * usage.input + price_out * usage.output) / _MILLION
    unit_key = (usage.service, usage.unit)
    if unit_key not in _UNIT_PRICES:
        raise UnknownPrice(f"no unit price for {usage.service}/{usage.unit}")
    return _UNIT_PRICES[unit_key] * usage.count
