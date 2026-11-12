from decimal import Decimal

import pytest

from app.budget import Tokens, Units, UnknownPrice, estimate_cost


def test_tokens_are_priced_per_million_by_direction() -> None:
    # Worked example: 2M input at 3 USD/M plus 0.5M output at 15 USD/M = 6 + 7.5.
    usage = Tokens(service="anthropic", model="claude-sonnet", input=2_000_000, output=500_000)

    assert estimate_cost(usage) == Decimal("13.5")


def test_units_are_priced_per_unit() -> None:
    # 1000 Places autocomplete requests at 0.00283 USD each.
    usage = Units(service="google_places", unit="autocomplete_request", count=1000)

    assert estimate_cost(usage) == Decimal("2.83")


def test_zero_usage_costs_nothing() -> None:
    assert estimate_cost(Units(service="apify", unit="review", count=0)) == Decimal(0)


@pytest.mark.parametrize(
    "usage",
    [
        Tokens(service="anthropic", model="no-such-model", input=1, output=1),
        Tokens(service="no-such-service", model="claude-sonnet", input=1, output=1),
        Units(service="apify", unit="no-such-unit", count=1),
    ],
)
def test_an_unpriced_service_is_refused_not_free(usage: Tokens | Units) -> None:
    with pytest.raises(UnknownPrice):
        estimate_cost(usage)


def test_negative_usage_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        Units(service="apify", unit="review", count=-1)
    with pytest.raises(ValueError, match="negative"):
        Tokens(service="anthropic", model="claude-sonnet", input=-1, output=0)
