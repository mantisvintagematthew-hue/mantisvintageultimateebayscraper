from __future__ import annotations

import json
import re
from pathlib import Path
from sqlalchemy import select

from app.db.schema import Image, Listing, ListingImage
from app.pipeline.extract_declared import extract_declared_date
from app.pipeline.infer_date import infer_date
from app.pipeline.ocr_tag import ocr_tag_image
from app.pipeline.resolve_date import resolve_dates
from app.vision.stitch_detect import detect_single_stitch


REGION_PATTERNS = {
    "USA": [r"made in usa", r"made in u\.?s\.?a\.?", r"made in united states"],
    "Mexico": [r"made in mexico"],
    "Honduras": [r"made in honduras"],
    "Nicaragua": [r"made in nicaragua"],
    "Haiti": [r"made in haiti"],
}

BRAND_PATTERNS = {
    "screen stars": [r"screen\s*stars"],
    "hanes": [r"\bhanes\b", r"hanes\s+beefy"],
    "fruit of the loom": [r"fruit\s+of\s+the\s+loom"],
    "anvil": [r"\banvil\b"],
    "brockum": [r"\bbrockum\b"],
    "gildan": [r"\bgildan\b"],
}


def process_listing(repo, listing: Listing) -> None:
    raw_payload = _load_json(Path(listing.raw_json_path))
    description = listing.description or raw_payload.get("description") or ""
    specifics_text = _specifics_to_text(raw_payload)
    declared = extract_declared_date(listing.title, description, specifics_text)

    tag_link = repo.session.scalar(
        select(ListingImage).where(ListingImage.listing_id == listing.id, ListingImage.role == "tag")
    )
    hero_link = repo.session.scalar(
        select(ListingImage).where(ListingImage.listing_id == listing.id, ListingImage.role == "hero")
    )
    tag_text = ""
    single_stitch = False
    if tag_link:
        tag_img = repo.session.get(Image, tag_link.image_id)
        if tag_img:
            tag_text = ocr_tag_image(Path(tag_img.local_path))
    if hero_link:
        hero_img = repo.session.get(Image, hero_link.image_id)
        if hero_img:
            single_stitch = detect_single_stitch(Path(hero_img.local_path))

    combined_text = f"{listing.title or ''} {description} {specifics_text} {tag_text}"
    brand = _extract_brand(combined_text)
    made_in = _extract_made_in(combined_text)
    region = _normalize_region(made_in)

    repo.upsert_extraction(
        listing.id,
        brand_raw=brand,
        made_in_raw=made_in,
        region_normalized=region,
        tag_text_ocr=tag_text,
        declared_text=declared.snippet,
        declared_source=declared.source,
        declared_year=declared.declared_year,
        declared_start_year=declared.start_year,
        declared_end_year=declared.end_year,
        declared_confidence=declared.confidence,
    )
    inferred = infer_date(tag_text=tag_text, made_in_raw=made_in, single_stitch_positive=single_stitch)
    repo.upsert_inference(listing.id, **inferred)
    resolution = resolve_dates(
        {
            "declared_year": declared.declared_year,
            "declared_start_year": declared.start_year,
            "declared_end_year": declared.end_year,
            "declared_confidence": declared.confidence,
        },
        inferred,
    )
    repo.upsert_resolution(listing.id, **resolution)


def _extract_brand(text: str) -> str | None:
    lower = text.lower()
    for brand, patterns in BRAND_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, lower):
                return brand
    return None


def _extract_made_in(text: str) -> str | None:
    lower = text.lower()
    for patterns in REGION_PATTERNS.values():
        for pattern in patterns:
            m = re.search(pattern, lower)
            if m:
                start, end = m.span()
                return text[start:end]
    return None


def _normalize_region(made_in_raw: str | None) -> str | None:
    if not made_in_raw:
        return None
    lower = made_in_raw.lower()
    for region, patterns in REGION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, lower):
                return region
    return None


def _specifics_to_text(payload: dict) -> str:
    parts: list[str] = []
    for item in payload.get("localizedAspects", []) or []:
        name = item.get("name") or ""
        values = ", ".join(item.get("value", []) or [])
        if name or values:
            parts.append(f"{name}: {values}".strip())
    return " | ".join(parts)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def export_jsonl(session, out_path: Path) -> int:
    from app.db.schema import DateInference, DateResolution, Extraction

    rows = session.execute(
        select(Listing, Extraction, DateInference, DateResolution)
        .join(Extraction, Listing.id == Extraction.listing_id, isouter=True)
        .join(DateInference, Listing.id == DateInference.listing_id, isouter=True)
        .join(DateResolution, Listing.id == DateResolution.listing_id, isouter=True)
    ).all()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for listing, extraction, inferred, resolved in rows:
            record = {
                "listing_id": listing.id,
                "ebay_item_id": listing.ebay_item_id,
                "title": listing.title,
                "needs_review": listing.needs_review,
                "extraction": _model_to_public_dict(extraction),
                "inference": _model_to_public_dict(inferred),
                "resolution": _model_to_public_dict(resolved),
            }
            f.write(json.dumps(record) + "\n")
    return len(rows)


def _model_to_public_dict(model_obj):
    if model_obj is None:
        return None
    data = {}
    for key, value in model_obj.__dict__.items():
        if key.startswith("_"):
            continue
        data[key] = value
    return data
