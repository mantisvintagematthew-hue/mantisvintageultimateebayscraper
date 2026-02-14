from __future__ import annotations

import json

TAG_FAMILY_MAP = {
    "screen stars": (1983, 1992),
    "fruit of the loom best": (1988, 1995),
    "hanes beefy": (1987, 1998),
}


def infer_date(tag_text: str | None, made_in_raw: str | None, single_stitch_positive: bool) -> dict:
    start, end = 1975, 2005
    confidence = 0.2
    evidence: list[str] = []
    lower = (tag_text or "").lower()
    if "made in usa" in lower or "made in usa" in (made_in_raw or "").lower():
        start, end = max(start, 1978), min(end, 1999)
        confidence += 0.2
        evidence.append("made_in_usa_signal")
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
    inferred_year = (start + end) // 2 if start <= end else None
    return {
        "inferred_year": inferred_year,
        "inferred_start_year": start if start <= end else None,
        "inferred_end_year": end if start <= end else None,
        "inferred_confidence": min(confidence, 0.99),
        "evidence_json": json.dumps(evidence),
    }
