import json

from app.pipeline.infer_date import infer_date


def test_infer_date_with_region_and_tag_family():
    out = infer_date("Screen Stars Best", "Made in USA", single_stitch_positive=True)
    assert out["inferred_start_year"] <= out["inferred_end_year"]
    evidence = json.loads(out["evidence_json"])
    assert any(e.startswith("tag_family:") for e in evidence)
    assert "made_in_usa_signal" in evidence


def test_infer_date_conflicting_signals_fallback():
    out = infer_date("Screen Stars Best", "Made in Honduras", single_stitch_positive=True)
    # still returns a valid range
    assert out["inferred_start_year"] <= out["inferred_end_year"]
