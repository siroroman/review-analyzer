from tests.api.helpers import ADMIN, DEMO, HEADERS, Api


def test_a_request_without_a_token_is_401() -> None:
    assert Api().client.get("/places/suggest", params={"q": "kav"}).status_code == 401


def test_a_wrong_token_is_401() -> None:
    api = Api()
    response = api.client.get(
        "/places/suggest", params={"q": "kav"}, headers={"Authorization": "Bearer nope"}
    )
    assert response.status_code == 401


def test_a_header_that_is_not_a_bearer_token_is_401() -> None:
    api = Api()
    response = api.client.get("/places/suggest", params={"q": "kav"}, headers={"Authorization": DEMO})
    assert response.status_code == 401


def test_a_demo_token_is_accepted() -> None:
    api = Api()
    assert api.client.get("/places/suggest", params={"q": "kav"}, headers=HEADERS).status_code == 200


def test_the_401_does_not_echo_the_token() -> None:
    api = Api()
    response = api.client.get(
        "/places/suggest", params={"q": "kav"}, headers={"Authorization": "Bearer s3cret-guess"}
    )
    assert "s3cret-guess" not in response.text


def test_a_demo_token_never_opens_admin_routes() -> None:
    api = Api()
    assert api.client.get("/admin/spend", headers=HEADERS).status_code == 401


def test_admin_routes_are_closed_without_a_token() -> None:
    assert Api().client.get("/admin/spend").status_code == 401


def test_the_admin_token_passes_the_gate_but_is_not_a_demo_token() -> None:
    api = Api()
    admin = {"Authorization": f"Bearer {ADMIN}"}
    assert api.client.get("/admin/spend", headers=admin).status_code == 404  # no route yet: #44 adds them
    assert api.client.get("/places/suggest", params={"q": "kav"}, headers=admin).status_code == 401


def test_without_a_configured_admin_token_admin_routes_stay_closed() -> None:
    api = Api(admin_token=None)
    assert api.client.get("/admin/spend", headers={"Authorization": f"Bearer {ADMIN}"}).status_code == 401


def test_the_openapi_description_is_public() -> None:
    assert Api().client.get("/openapi.json").status_code == 200
