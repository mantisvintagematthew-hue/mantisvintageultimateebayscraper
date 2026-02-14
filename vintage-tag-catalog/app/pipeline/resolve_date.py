from __future__ import annotations


def resolve_dates(declared: dict, inferred: dict) -> dict:
    dy = declared.get("declared_year")
    ds, de = declared.get("declared_start_year"), declared.get("declared_end_year")
    is_, ie = inferred.get("inferred_start_year"), inferred.get("inferred_end_year")
    iy = inferred.get("inferred_year")

    if dy is not None and is_ is not None and ie is not None:
        if is_ <= dy <= ie:
            return {
                "canonical_year": dy,
                "canonical_start_year": ds or is_,
                "canonical_end_year": de or ie,
                "canonical_confidence": max(declared.get("declared_confidence") or 0, inferred.get("inferred_confidence") or 0),
                "conflict_flag": False,
                "resolution_reason": "declared_within_inferred",
            }
        return {
            "canonical_year": iy,
            "canonical_start_year": is_,
            "canonical_end_year": ie,
            "canonical_confidence": inferred.get("inferred_confidence") or 0,
            "conflict_flag": True,
            "resolution_reason": "declared_conflicts_inferred",
        }

    if ds is not None and de is not None and is_ is not None and ie is not None:
        lo, hi = max(ds, is_), min(de, ie)
        if lo <= hi:
            return {
                "canonical_year": iy,
                "canonical_start_year": lo,
                "canonical_end_year": hi,
                "canonical_confidence": inferred.get("inferred_confidence") or 0,
                "conflict_flag": False,
                "resolution_reason": "declared_range_overlaps_inferred",
            }

    return {
        "canonical_year": iy,
        "canonical_start_year": is_,
        "canonical_end_year": ie,
        "canonical_confidence": inferred.get("inferred_confidence") or 0,
        "conflict_flag": False,
        "resolution_reason": "default_inferred",
    }
