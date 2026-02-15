from app.pipeline.extract_pipeline import _extract_brand, _normalize_region


def test_brand_normalization_regex():
    assert _extract_brand("Vintage tee on Fruit of the Loom tag") == "fruit of the loom"


def test_region_normalization_regex():
    assert _normalize_region("made in u.s.a") == "USA"
    assert _normalize_region("made in nicaragua") == "Nicaragua"
