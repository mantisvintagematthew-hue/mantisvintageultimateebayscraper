from pathlib import Path

from typer.testing import CliRunner

from app.cli import app


runner = CliRunner()


def test_api_mode_fixture_lane_integration(tmp_path: Path):
    env = {
        "DATABASE_URL": f"sqlite:///{tmp_path/'vtc.db'}",
        "VTC_DATA_DIR": str(tmp_path / "data"),
    }
    fixture = Path(__file__).parent / "fixtures" / "ebay_search.json"
    res = runner.invoke(
        app,
        ["run-all", "--mode", "api", "--query", "vintage tee", "--limit", "1", "--fixture", str(fixture), "--since-hours", "72"],
        env=env,
    )
    assert res.exit_code == 0

    metrics_out = tmp_path / "metrics.json"
    metrics_res = runner.invoke(app, ["metrics", "--out", str(metrics_out)], env=env)
    assert metrics_res.exit_code == 0
    assert metrics_out.exists()


def test_web_mode_fixture_lane_integration(tmp_path: Path):
    env = {
        "DATABASE_URL": f"sqlite:///{tmp_path/'vtc.db'}",
        "VTC_DATA_DIR": str(tmp_path / "data"),
    }
    html_fixture = Path(__file__).parent / "fixtures" / "web" / "ebay_search_sample.html"
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
            "--web-fixture-html",
            str(html_fixture),
        ],
        env=env,
    )
    assert res.exit_code == 0
    qa_out = tmp_path / "qa.jsonl"
    qa_res = runner.invoke(app, ["qa-sample", "--sample-size", "2", "--out", str(qa_out)], env=env)
    assert qa_res.exit_code == 0
    assert qa_out.exists()
