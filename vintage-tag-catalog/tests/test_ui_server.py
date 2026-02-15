from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.ui import server


client = TestClient(server.app)


def test_ui_collect_rejects_web_limit_over_50():
    res = client.post("/collect", data={"query": "vintage tee", "mode": "web", "limit": "80"})
    assert res.status_code == 400
    assert "between 1 and 50" in res.text


def test_ui_collect_handles_web_503(monkeypatch, tmp_path: Path):
    class DummyOrchestrator:
        def __init__(self, *_args, **_kwargs):
            pass

        def collect_web(self, *_args, **_kwargs):
            req = httpx.Request("GET", "https://www.ebay.com/sch/i.html?_nkw=vintage")
            resp = httpx.Response(503, request=req)
            raise httpx.HTTPStatusError("503", request=req, response=resp)

    class DummyRepo:
        def __init__(self, *_args, **_kwargs):
            pass

        def create_collect_run(self, **_kwargs):
            return None

        def finish_collect_run(self, **_kwargs):
            return None

    class DummySession:
        def commit(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class DummyFactory:
        def __call__(self):
            return DummySession()

    monkeypatch.setattr(server, "CollectionOrchestrator", DummyOrchestrator)
    monkeypatch.setattr(server, "Repo", DummyRepo)
    monkeypatch.setattr(server, "make_session_factory", lambda *_args, **_kwargs: DummyFactory())
    monkeypatch.setattr(
        server,
        "get_settings",
        lambda: type("S", (), {"database_url": f"sqlite:///{tmp_path/'db.sqlite'}", "data_dir": tmp_path, "ebay_client_id": "", "ebay_client_secret": "", "ebay_marketplace": "EBAY_US"})(),
    )

    res = client.post("/collect", data={"query": "vintage tee", "mode": "web", "limit": "1"})
    assert res.status_code == 503
    assert "HTTP 503" in res.text
