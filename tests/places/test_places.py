from datetime import timedelta

import pytest

from app.domain import Company
from app.gateway import ClientError, ClientTimeout, Suggestion, TextSearchRequest
from app.places import EmptyCompany, InvalidCompany, PlaceNotFound, PlacesUnavailable
from tests.places.helpers import RUN, Setup, firmy, google, pages


def test_suggest_returns_the_places_google_proposes() -> None:
    setup = Setup()
    setup.google.suggestions["glob"] = (Suggestion("g1", "Globus, Praha"), Suggestion("g2", "Globus, Brno"))
    assert setup.places.suggest("glob", run_id=RUN) == [
        Suggestion("g1", "Globus, Praha"),
        Suggestion("g2", "Globus, Brno"),
    ]


def test_suggest_for_a_blank_query_makes_no_call() -> None:
    setup = Setup()
    assert setup.places.suggest("   ", run_id=RUN) == []
    assert setup.google.client.calls == []


def test_suggest_with_no_result_is_an_empty_list() -> None:
    assert Setup().places.suggest("zzzz", run_id=RUN) == []


def test_resolve_returns_the_place_for_a_google_id() -> None:
    setup = Setup()
    setup.google.known["g1"] = google("g1", "Camp Velo", "Vratěnín 92")
    assert setup.places.resolve("g1", run_id=RUN) == google("g1", "Camp Velo", "Vratěnín 92")


def test_resolve_of_an_unknown_id_is_place_not_found() -> None:
    with pytest.raises(PlaceNotFound):
        Setup().places.resolve("nope", run_id=RUN)


def test_branches_are_the_other_places_of_the_name_without_the_place_itself() -> None:
    setup = Setup()
    home = google("g1", "Globus Hypermarket", "Čakovice")
    setup.google.pages = pages([home, google("g2", address="Zličín")], [google("g3", address="Černý Most")])
    found = setup.places.branches(home, run_id=RUN)
    assert [place.external_id for place in found] == ["g2", "g3"]
    asked = setup.google.asked("text_search")
    assert asked == [
        TextSearchRequest("Globus Hypermarket"),
        TextSearchRequest("Globus Hypermarket", "next-0"),
    ]


def test_branches_with_the_exact_name_come_before_other_places_of_the_chain() -> None:
    setup = Setup()
    home = google("g1", "Globus Hypermarket")
    setup.google.pages = pages(
        [
            google("g2", "Restaurace Globus"),
            google("g3", "globus hypermarket"),
            google("g4", "Globus čerpací stanice"),
            google("g5", "Globus Hypermarket"),
        ]
    )
    assert [place.external_id for place in setup.places.branches(home, run_id=RUN)] == [
        "g3",
        "g5",
        "g2",
        "g4",
    ]


def test_branches_lists_a_place_once_and_stops_after_three_pages() -> None:
    setup = Setup()
    home = google("g1")
    setup.google.pages = pages(
        [google("g2"), google("g2")], [google("g3")], [google("g4")], [google("g5")], [google("g6")]
    )
    assert [place.external_id for place in setup.places.branches(home, run_id=RUN)] == ["g2", "g3", "g4"]
    assert len(setup.google.asked("text_search")) == 3


def test_branches_without_a_result_is_empty() -> None:
    assert Setup().places.branches(google("g1"), run_id=RUN) == []


def test_the_same_set_of_places_in_any_order_is_one_company() -> None:
    setup = Setup()
    for external_id in ("g1", "g2", "g3"):
        setup.google.known[external_id] = google(external_id, address=external_id)
    first = setup.places.confirm(["g1", "g2", "g3"], name="Globus", industry="retail", run_id=RUN)
    second = setup.places.confirm(["g3", "g1", "g2", "g1"], name="Globus CZ", industry="retail", run_id=RUN)
    assert isinstance(first, Company)
    assert first.places_key == second.places_key


def test_a_different_set_of_places_is_another_company() -> None:
    setup = Setup()
    for external_id in ("g1", "g2"):
        setup.google.known[external_id] = google(external_id)
    both = setup.places.confirm(["g1", "g2"], name="Globus", industry="retail", run_id=RUN)
    one = setup.places.confirm(["g1"], name="Globus", industry="retail", run_id=RUN)
    assert both.places_key != one.places_key


def test_an_empty_set_is_rejected_without_a_call() -> None:
    setup = Setup()
    with pytest.raises(EmptyCompany):
        setup.places.confirm([], name="Globus", industry="retail", run_id=RUN)
    assert setup.google.client.calls == []


def test_a_confirmed_company_holds_the_resolved_and_the_matched_places() -> None:
    setup = Setup()
    setup.google.known["g1"] = google("g1", "Globus Hypermarket", "Čakovice")
    on_firmy = firmy("f1", "Globus Hypermarket", "Kostelecká 823, Praha-Čakovice")
    company = setup.places.confirm(["g1"], name="Globus", industry="retail", run_id=RUN, also=[on_firmy])
    assert company.name == "Globus"
    assert company.industry == "retail"
    assert company.places == (google("g1", "Globus Hypermarket", "Čakovice"), on_firmy)


def test_confirming_an_unknown_id_is_place_not_found() -> None:
    with pytest.raises(PlaceNotFound):
        Setup().places.confirm(["nope"], name="Globus", industry="retail", run_id=RUN)


def test_match_other_sources_ranks_by_name_and_address() -> None:
    home = google("g1", "Globus Hypermarket", "Kostelecká 823, 196 00 Praha-Čakovice")
    right = firmy("f1", "Globus hypermarket", "Kostelecká 823, Praha - Čakovice")
    same_name_elsewhere = firmy("f2", "Globus Hypermarket", "Sárská 5, Praha-Zličín")
    unrelated = firmy("f3", "Potraviny Novák", "Kostelecká 12, Praha")
    setup = Setup([same_name_elsewhere, unrelated, right])
    assert setup.places.match_other_sources(home) == [right, same_name_elsewhere]
    assert setup.other.asked == [("Globus Hypermarket", "Kostelecká 823, 196 00 Praha-Čakovice")]


def test_match_other_sources_ignores_diacritics_and_case() -> None:
    home = google("g1", "U Bílého Anděla", "Masarykovo nám. 42/26, Nový Jičín")
    candidate = firmy("f1", "U BILEHO ANDELA", "Masarykovo nam. 42, Novy Jicin")
    assert Setup([candidate]).places.match_other_sources(home) == [candidate]


def test_match_other_sources_with_no_candidate_is_empty() -> None:
    assert Setup().places.match_other_sources(google("g1")) == []


def test_other_source_outage_is_a_try_later_result() -> None:
    with pytest.raises(PlacesUnavailable):
        Setup(other_fails=True).places.match_other_sources(google("g1"))


@pytest.mark.parametrize("failure", [ClientTimeout(), ClientError("unavailable"), ClientError("network")])
def test_a_google_outage_is_a_try_later_result(failure: Exception) -> None:
    setup = Setup()
    setup.google.error = failure
    with pytest.raises(PlacesUnavailable):
        setup.places.suggest("glob", run_id=RUN)
    with pytest.raises(PlacesUnavailable):
        setup.places.resolve("g1", run_id=RUN)
    with pytest.raises(PlacesUnavailable):
        setup.places.branches(google("g1"), run_id=RUN)


def test_a_rate_limit_of_the_gateway_is_a_try_later_result_with_the_wait() -> None:
    setup = Setup(max_calls=1)
    setup.places.suggest("glob", run_id=RUN)
    with pytest.raises(PlacesUnavailable) as later:
        setup.places.suggest("glob", run_id=RUN)
    assert later.value.reason == "rate_limited"
    assert later.value.retry_after == timedelta(seconds=60)


def test_an_exceeded_budget_is_a_try_later_result_and_makes_no_call() -> None:
    setup = Setup(run_cap="0.01")  # one details request costs 0.017 USD
    with pytest.raises(PlacesUnavailable) as later:
        setup.places.resolve("g1", run_id=RUN)
    assert later.value.reason == "budget_exceeded"
    assert setup.google.client.calls == []


def test_a_request_or_key_google_rejects_is_a_fault_not_a_try_later() -> None:
    setup = Setup()
    setup.google.error = ClientError("rejected")
    with pytest.raises(ClientError):
        setup.places.suggest("glob", run_id=RUN)


def test_an_id_that_is_not_an_id_is_place_not_found() -> None:
    setup = Setup()
    setup.google.error = ClientError("bad_request")
    with pytest.raises(PlaceNotFound):
        setup.places.resolve("not/an/id", run_id=RUN)


@pytest.mark.parametrize(("name", "industry"), [(" ", "retail"), ("Globus", "")])
def test_a_company_without_a_name_or_industry_is_rejected_before_any_paid_call(
    name: str, industry: str
) -> None:
    setup = Setup()
    with pytest.raises(InvalidCompany):
        setup.places.confirm(["g1"], name=name, industry=industry, run_id=RUN)
    assert setup.google.client.calls == []


def test_a_place_listed_twice_is_rejected_before_any_paid_call() -> None:
    setup = Setup()
    twice = firmy("f1", "Globus", "Praha")
    with pytest.raises(InvalidCompany):
        setup.places.confirm(["g1"], name="G", industry="retail", run_id=RUN, also=[twice, twice])
    with pytest.raises(InvalidCompany):
        setup.places.confirm(["g1"], name="G", industry="retail", run_id=RUN, also=[google("g1")])
    assert setup.google.client.calls == []


def test_a_company_of_only_other_source_places_needs_no_google_call() -> None:
    setup = Setup()
    company = setup.places.confirm(
        [], name="G", industry="retail", run_id=RUN, also=[firmy("f1", "G", "Praha")]
    )
    assert [place.external_id for place in company.places] == ["f1"]
    assert setup.google.client.calls == []
