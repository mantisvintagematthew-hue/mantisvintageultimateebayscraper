from __future__ import annotations

import json

TAG_FAMILY_MAP = {
    "screen stars": (1983, 1992),
    "screen stars best": (1985, 1993),
    "fruit of the loom best": (1988, 1995),
    "hanes beefy": (1987, 1998),
    "anvil": (1990, 2005),
    "brockum": (1988, 1998),
}

REGION_SIGNALS = {
    "made in usa": (1978, 1999, "made_in_usa_signal", 0.20),
    "made in mexico": (1992, 2008, "made_in_mexico_signal", 0.12),
    "made in honduras": (1995, 2012, "made_in_honduras_signal", 0.12),
}


def infer_date(tag_text: str | None, made_in_raw: str | None, single_stitch_positive: bool) -> dict:
    start, end = 1975, 2005
    confidence = 0.2
    evidence: list[str] = []
    lower = ((tag_text or "") + " " + (made_in_raw or "")).lower()

    for token, (s, e, ev, conf) in REGION_SIGNALS.items():
        if token in lower:
            start, end = max(start, s), min(end, e)
            confidence += conf
            evidence.append(ev)
            break

    if single_stitch_positive:
        start, end = max(start, 1980), min(end, 1998)
        confidence += 0.25
        evidence.append("single_stitch_positive")

    for family, (f_start, f_end) in TAG_FAMILY_MAP.items():
        if family in lower:
            start, end = max(start, f_start), min(end, f_end)
            confidence += 0.35
            evidence.append(f"tag_family:{family}")
            break

    if start > end:
        start, end = 1975, 2005
        confidence = min(confidence, 0.35)
        evidence.append("signal_conflict_fallback")

    inferred_year = (start + end) // 2
    return {
        "inferred_year": inferred_year,
        "inferred_start_year": start,
        "inferred_end_year": end,
        "inferred_confidence": min(confidence, 0.99),
        "evidence_json": json.dumps(evidence),
    }
