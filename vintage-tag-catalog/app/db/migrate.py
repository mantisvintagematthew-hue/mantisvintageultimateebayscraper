from __future__ import annotations

from sqlalchemy import inspect, text

from app.db.schema import Base, make_engine


def migrate(database_url: str) -> None:
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)

    # lightweight compatibility migration for older DBs
    with engine.begin() as conn:
        insp = inspect(conn)
        listing_cols = {c["name"] for c in insp.get_columns("listings")}
        if "source_mode" not in listing_cols:
            conn.execute(text("ALTER TABLE listings ADD COLUMN source_mode VARCHAR DEFAULT 'api'"))
