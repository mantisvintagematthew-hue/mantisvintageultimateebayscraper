from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ebay_item_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    url: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_path: Mapped[str | None] = mapped_column(String, nullable=True)
    seller_username: Mapped[str | None] = mapped_column(String, nullable=True)
    price_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_currency: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    raw_json_path: Mapped[str] = mapped_column(String)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)

    images: Mapped[list[Image]] = relationship(back_populates="listing")


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    source_url: Mapped[str] = mapped_column(String)
    local_path: Mapped[str] = mapped_column(String)
    sha256: Mapped[str] = mapped_column(String, unique=True, index=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    listing: Mapped[Listing] = relationship(back_populates="images")


class ListingImage(Base):
    __tablename__ = "listing_images"
    __table_args__ = (UniqueConstraint("listing_id", "role", name="uq_listing_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id"), index=True)
    role: Mapped[str] = mapped_column(String)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)


class Extraction(Base):
    __tablename__ = "extractions"

    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), primary_key=True)
    brand_raw: Mapped[str | None] = mapped_column(String, nullable=True)
    made_in_raw: Mapped[str | None] = mapped_column(String, nullable=True)
    region_normalized: Mapped[str | None] = mapped_column(String, nullable=True)
    tag_text_ocr: Mapped[str | None] = mapped_column(Text, nullable=True)
    declared_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    declared_source: Mapped[str | None] = mapped_column(String, nullable=True)
    declared_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    declared_start_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    declared_end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    declared_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class DateInference(Base):
    __tablename__ = "date_inference"

    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), primary_key=True)
    inferred_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inferred_start_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inferred_end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inferred_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_json: Mapped[str] = mapped_column(Text)


class DateResolution(Base):
    __tablename__ = "date_resolution"

    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), primary_key=True)
    canonical_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    canonical_start_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    canonical_end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    canonical_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    conflict_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_reason: Mapped[str] = mapped_column(Text)



def make_engine(database_url: str):
    return create_engine(database_url, future=True)



def make_session_factory(database_url: str):
    return sessionmaker(bind=make_engine(database_url), expire_on_commit=False)
