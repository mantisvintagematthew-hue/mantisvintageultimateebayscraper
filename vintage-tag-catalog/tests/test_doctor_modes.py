from pathlib import Path

from typer.testing import CliRunner

from app.cli import app


runner = CliRunner()


def test_doctor_web_mode_uses_health_check(monkeypatch, tmp_path: Path):
    env = {
        "DATABASE_URL": f"sqlite:///{tmp_path/'vtc.db'}",
        "VTC_DATA_DIR": str(tmp_path / "data"),
    }

    from app import cli as cli_module

    class StubCollector:
        def check_health(self, query: str = "vintage single stitch t shirt"):
            return {"robots_ok": True, "reachability_ok": True, "selectors_ok": True, "ok": True, "detail": ""}

    monkeypatch.setattr(cli_module, "EbayWebCollector", StubCollector)
    res = runner.invoke(app, ["doctor", "--mode", "web"], env=env)
    assert res.exit_code == 0
    assert "web_robots_ok" in res.stdout
