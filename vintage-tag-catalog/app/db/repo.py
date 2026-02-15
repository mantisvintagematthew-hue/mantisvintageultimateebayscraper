from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy import select

from app.db.schema import (
    DateInference,
    DateResolution,
    Extraction,
    Image,
    Listing,
    ListingImage,
)


class Repo:
    def __init__(self, session):
        self.session = session

    def upsert_listing(self, payload: dict, raw_json_path: str) -> Listing:
        ebay_item_id = payload["itemId"]
        listing = self.session.scalar(select(Listing).where(Listing.ebay_item_id == ebay_item_id))
        if listing is None:
            listing = Listing(
                ebay_item_id=ebay_item_id,
                url=payload.get("itemWebUrl", ""),
                title=payload.get("title", ""),
                description=payload.get("shortDescription") or payload.get("description"),
                category_path=payload.get("categoryPath"),
                seller_username=(payload.get("seller") or {}).get("username"),
                price_value=_float_or_none(((payload.get("price") or {}).get("value"))),
                price_currency=((payload.get("price") or {}).get("currency")),
                location=payload.get("itemLocation", {}).get("country"),
                raw_json_path=raw_json_path,
            )
            self.session.add(listing)
        else:
            listing.title = payload.get("title", listing.title)
            listing.description = payload.get("shortDescription") or payload.get("description") or listing.description
            listing.updated_at = datetime.utcnow()
            listing.raw_json_path = raw_json_path
        self.session.flush()
        return listing

    def recent_listings(self, since_hours: int) -> list[Listing]:
        cutoff = datetime.utcnow() - timedelta(hours=since_hours)
        stmt = select(Listing).where(Listing.created_at >= cutoff)
        return list(self.session.scalars(stmt))

    def add_image(self, listing_id: int, source_url: str, local_path: str, sha256: str, width: int | None, height: int | None) -> Image:
        existing = self.session.scalar(select(Image).where(Image.sha256 == sha256))
        if existing:
            return existing
        img = Image(
            listing_id=listing_id,
            source_url=source_url,
            local_path=local_path,
            sha256=sha256,
            width=width,
            height=height,
        )
        self.session.add(img)
        self.session.flush()
        return img

    def set_listing_role_image(self, listing_id: int, image_id: int, role: str, score: float) -> None:
        row = self.session.scalar(
            select(ListingImage).where(ListingImage.listing_id == listing_id, ListingImage.role == role)
        )
        if row is None:
            row = ListingImage(listing_id=listing_id, image_id=image_id, role=role, score=score)
            self.session.add(row)
        else:
            row.image_id = image_id
            row.score = score

    def set_needs_review(self, listing_id: int, needs_review: bool) -> None:
        listing = self.session.get(Listing, listing_id)
        if listing:
            listing.needs_review = needs_review

    def upsert_extraction(self, listing_id: int, **kwargs) -> None:
        obj = self.session.get(Extraction, listing_id)
        if obj is None:
            obj = Extraction(listing_id=listing_id, **kwargs)
            self.session.add(obj)
        else:
            for k, v in kwargs.items():
                setattr(obj, k, v)

    def upsert_inference(self, listing_id: int, **kwargs) -> None:
        obj = self.session.get(DateInference, listing_id)
        if obj is None:
            obj = DateInference(listing_id=listing_id, **kwargs)
            self.session.add(obj)
        else:
            for k, v in kwargs.items():
                setattr(obj, k, v)

    def upsert_resolution(self, listing_id: int, **kwargs) -> None:
        obj = self.session.get(DateResolution, listing_id)
        if obj is None:
            obj = DateResolution(listing_id=listing_id, **kwargs)
            self.session.add(obj)
        else:
            for k, v in kwargs.items():
                setattr(obj, k, v)



def _float_or_none(v):
    try:
        return float(v)
    except Exception:
        return None
