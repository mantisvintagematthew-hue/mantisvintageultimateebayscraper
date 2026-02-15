from app.pipeline.extract_declared import extract_declared_date


def test_extract_explicit_year():
    out = extract_declared_date("Vintage 1992 tour shirt", "")
    assert out.declared_year == 1992
    assert out.start_year == 1992


def test_extract_range():
    out = extract_declared_date("", "dated 1992-1994 era")
    assert out.declared_year is None
    assert out.start_year == 1992
    assert out.end_year == 1994


def test_extract_decade_late_90s():
    out = extract_declared_date("late 90s rap tee", "")
    assert out.start_year == 1996
    assert out.end_year == 1999


def test_extract_specifics_field_when_title_description_empty():
    out = extract_declared_date("", "", "Era: Early 90s")
    assert out.source == "specifics"
    assert out.start_year == 1990
    assert out.end_year == 1993
