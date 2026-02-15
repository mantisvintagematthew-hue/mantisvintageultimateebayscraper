from __future__ import annotations

from datetime import timedelta
from sqlalchemy import select

from app.db.schema import CollectRun, DateInference, DateResolution, Extraction, Image, Listing, ListingImage, utcnow


class Repo:
    def __init__(self, session):
        self.session = session

    def create_collect_run(self, run_id: str, mode: str, query: str, limit: int) -> CollectRun:
        row = CollectRun(run_id=run_id, mode=mode, query=query, limit=limit, status="started")
        self.session.add(row)
        self.session.flush()
        return row

    def finish_collect_run(self, run_id: str, status: str, collected_count: int, error_message: str | None = None) -> None:
        row = self.session.scalar(select(CollectRun).where(CollectRun.run_id == run_id))
        if row:
            row.status = status
            row.collected_count = collected_count
            row.error_message = error_message
            row.updated_at = utcnow()

    def upsert_listing(self, payload: dict, raw_json_path: str, source_mode: str = "api") -> Listing:
        ebay_item_id = payload["itemId"]
        listing = self.session.scalar(select(Listing).where(Listing.ebay_item_id == ebay_item_id))

        seller = _as_dict(payload.get("seller"))
        price = _as_dict(payload.get("price"))
        item_location = _as_dict(payload.get("itemLocation"))

        if listing is None:
            listing = Listing(
                ebay_item_id=ebay_item_id,
                source_mode=source_mode,
                url=payload.get("itemWebUrl", ""),
                title=payload.get("title", ""),
                description=payload.get("shortDescription") or payload.get("description"),
                category_path=payload.get("categoryPath"),
                seller_username=seller.get("username"),
                price_value=_float_or_none(price.get("value")),
                price_currency=price.get("currency"),
                location=item_location.get("country"),
                raw_json_path=raw_json_path,
            )
            self.session.add(listing)
        else:
            listing.source_mode = source_mode
            listing.title = payload.get("title", listing.title)
            listing.description = payload.get("shortDescription") or payload.get("description") or listing.description
            listing.updated_at = utcnow()
            listing.raw_json_path = raw_json_path
        self.session.flush()
        return listing

    def recent_listings(self, since_hours: int) -> list[Listing]:
        cutoff = utcnow() - timedelta(hours=since_hours)
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
        row = self.session.scalar(select(ListingImage).where(ListingImage.listing_id == listing_id, ListingImage.role == role))
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



def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}
