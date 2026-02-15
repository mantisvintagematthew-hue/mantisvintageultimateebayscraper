from pathlib import Path

from typer.testing import CliRunner

from app.cli import app


runner = CliRunner()


def test_collect_web_mode_rejects_large_limit(tmp_path: Path):
    env = {
        "DATABASE_URL": f"sqlite:///{tmp_path/'vtc.db'}",
        "VTC_DATA_DIR": str(tmp_path / "data"),
    }
    res = runner.invoke(app, ["collect", "--mode", "web", "--query", "vintage tee", "--limit", "80"], env=env)
    assert res.exit_code != 0


def test_run_all_web_mode_with_fixture_html(tmp_path: Path):
    env = {
        "DATABASE_URL": f"sqlite:///{tmp_path/'vtc.db'}",
        "VTC_DATA_DIR": str(tmp_path / "data"),
    }
    html_fixture = Path(__file__).parent / "fixtures" / "web" / "ebay_search_sample.html"
    res = runner.invoke(
        app,
        [
            "run-all",
            "--mode",
            "web",
            "--query",
            "vintage tee",
            "--limit",
            "25",
            "--web-fixture-html",
            str(html_fixture),
            "--since-hours",
            "72",
        ],
        env=env,
    )
    assert res.exit_code == 0
    assert "Run-all complete" in res.stdout


def test_collect_web_mode_rejects_listing_date_filters(tmp_path: Path):
    env = {
        "DATABASE_URL": f"sqlite:///{tmp_path/'vtc.db'}",
        "VTC_DATA_DIR": str(tmp_path / "data"),
    }
    res = runner.invoke(
        app,
        [
            "collect",
            "--mode",
            "web",
            "--query",
            "vintage tee",
            "--limit",
            "25",
            "--listed-after",
            "2024-01-01",
        ],
        env=env,
    )
    assert res.exit_code != 0
