from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import build_apps, build_service
from app.storage import in_memory_storage
from app.worker import FakeTokenVerifier
from tests.main.helpers import ENVIRON, Internet, clock

DEMO = {"Authorization": "Bearer demo-token-1"}
ADMIN = {"Authorization": "Bearer admin-token-1"}
VERIFIER = FakeTokenVerifier()


@pytest.fixture
def web(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>spa</html>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    return tmp_path


def service(web: Path) -> TestClient:
    wall = clock()
    built = build_apps(
        ENVIRON,
        transport=Internet(),
        storage=in_memory_storage(wall),
        clock=wall,
        token_verifier=VERIFIER,
    )
    return TestClient(build_service(built, web))


def test_the_spa_is_served_from_the_root(web: Path) -> None:
    client = service(web)
    assert client.get("/").text == "<html>spa</html>"
    assert client.get("/assets/app.js").text == "console.log(1)"


def test_a_client_route_falls_back_to_index_html(web: Path) -> None:
    client = service(web)
    answer = client.get("/result/abc")
    assert answer.status_code == 200
    assert answer.text == "<html>spa</html>"


def test_the_api_answers_under_api(web: Path) -> None:
    client = service(web)
    assert client.get("/api/places/suggest", params={"q": "x"}).status_code == 401
    assert client.get("/api/places/suggest", params={"q": "x"}, headers=DEMO).status_code == 200


def test_a_missing_api_route_is_a_404_not_the_spa(web: Path) -> None:
    assert service(web).get("/api/nope", headers=DEMO).status_code == 404


def test_the_admin_routes_need_the_admin_token_under_api_too(web: Path) -> None:
    client = service(web)
    for prefix in ("", "/api"):
        assert client.get(f"{prefix}/admin/spend", headers=DEMO).status_code == 401
        assert client.get(f"{prefix}/admin/spend", headers=ADMIN).status_code == 200


def test_tasks_run_reaches_the_worker_not_the_spa(web: Path) -> None:
    refused = service(web).post("/tasks/run", json={"run_id": "r1"})
    assert refused.status_code == 401


def test_the_lifespan_reaches_the_api(web: Path) -> None:
    wall = clock()
    built = build_apps(
        ENVIRON, transport=Internet(), storage=in_memory_storage(wall), clock=wall, token_verifier=VERIFIER
    )
    with TestClient(build_service(built, web)) as client:
        assert client.get("/").status_code == 200


def test_service_app_reads_the_environment_and_serves_web_dir(
    web: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wall = clock()
    built = build_apps(
        ENVIRON, transport=Internet(), storage=in_memory_storage(wall), clock=wall, token_verifier=VERIFIER
    )
    monkeypatch.setattr(main, "build_apps", lambda environ: built)
    monkeypatch.setenv("WEB_DIR", str(web))
    assert TestClient(main.service_app()).get("/").text == "<html>spa</html>"


def test_a_missing_asset_is_a_404_not_the_spa(web: Path) -> None:
    assert service(web).get("/assets/old-hash.js").status_code == 404
