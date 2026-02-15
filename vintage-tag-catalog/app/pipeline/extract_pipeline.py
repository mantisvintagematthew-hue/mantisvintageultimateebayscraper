from __future__ import annotations

import json
from pathlib import Path
from sqlalchemy import select

from app.db.schema import Image, Listing, ListingImage
from app.pipeline.extract_declared import extract_declared_date
from app.pipeline.infer_date import infer_date
from app.pipeline.ocr_tag import ocr_tag_image
from app.pipeline.resolve_date import resolve_dates
from app.vision.stitch_detect import detect_single_stitch


REGIONS = {
    "usa": "USA",
    "united states": "USA",
    "mexico": "Mexico",
    "honduras": "Honduras",
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
    for b in ["screen stars", "hanes", "fruit of the loom", "anvil", "brockum"]:
        if b in text.lower():
            return b
    return None


def _extract_made_in(text: str) -> str | None:
    lower = text.lower()
    if "made in" not in lower:
        return None
    idx = lower.find("made in")
    return text[idx : idx + 40]


def _normalize_region(made_in_raw: str | None) -> str | None:
    if not made_in_raw:
        return None
    lower = made_in_raw.lower()
    for k, v in REGIONS.items():
        if k in lower:
            return v
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
                "extraction": extraction.__dict__ if extraction else None,
                "inference": inferred.__dict__ if inferred else None,
                "resolution": resolved.__dict__ if resolved else None,
            }
            for k in ["extraction", "inference", "resolution"]:
                if record[k] and "_sa_instance_state" in record[k]:
                    record[k].pop("_sa_instance_state")
            f.write(json.dumps(record) + "\n")
    return len(rows)
