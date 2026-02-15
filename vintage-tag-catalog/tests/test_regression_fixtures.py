import json
from pathlib import Path

from app.pipeline.extract_pipeline import _specifics_to_text


def test_regression_search_fixture_collect_limit(tmp_path: Path):
    fixture = Path(__file__).parent / "fixtures" / "ebay_search_regression_realistic.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    assert len(payload["itemSummaries"]) == 2


def test_regression_item_fixture_specifics_text_contains_signals():
    fixture = Path(__file__).parent / "fixtures" / "ebay_get_item_regression_realistic.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    text = _specifics_to_text(payload).lower()
    assert "brand" in text
    assert "country/region of manufacture" in text
