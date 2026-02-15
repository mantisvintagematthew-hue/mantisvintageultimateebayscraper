from __future__ import annotations

from app.db.schema import Base, make_engine


def migrate(database_url: str) -> None:
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
