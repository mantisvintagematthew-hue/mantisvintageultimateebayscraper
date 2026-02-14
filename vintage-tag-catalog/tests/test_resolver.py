from app.pipeline.resolve_date import resolve_dates


def test_declared_inside_inferred():
    out = resolve_dates(
        {"declared_year": 1992, "declared_start_year": 1992, "declared_end_year": 1992, "declared_confidence": 0.9},
        {"inferred_year": 1993, "inferred_start_year": 1990, "inferred_end_year": 1995, "inferred_confidence": 0.7},
    )
    assert out["canonical_year"] == 1992
    assert not out["conflict_flag"]


def test_declared_conflict():
    out = resolve_dates(
        {"declared_year": 2008, "declared_start_year": 2008, "declared_end_year": 2008, "declared_confidence": 0.9},
        {"inferred_year": 1994, "inferred_start_year": 1991, "inferred_end_year": 1997, "inferred_confidence": 0.8},
    )
    assert out["canonical_year"] == 1994
    assert out["conflict_flag"]
