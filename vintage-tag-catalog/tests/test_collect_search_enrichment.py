from pathlib import Path

from sqlalchemy import select

from app.db.migrate import migrate
from app.db.repo import Repo
from app.db.schema import Listing, make_session_factory
from app.pipeline.collect import collect_search


class FakeBrowseClient:
    def __init__(self):
        self.search_calls = 0
        self.detail_calls = 0

    def search(self, query: str, limit: int = 200, offset: int = 0, filter_expr: str | None = None):
        self.search_calls += 1
        if offset > 0:
            return type("R", (), {"items": [], "raw": {}})()
        return type(
            "R",
            (),
            {
                "items": [
                    {"itemId": "v1|a|0", "title": "summary a", "itemWebUrl": "https://example.com/a"},
                    {"itemId": "v1|b|0", "title": "summary b", "itemWebUrl": "https://example.com/b"},
                ],
                "raw": {},
            },
        )()

    def get_item(self, item_id: str):
        self.detail_calls += 1
        return type(
            "D",
            (),
            {
                "item": {
                    "itemId": item_id,
                    "title": f"detail {item_id}",
                    "description": "Made in USA",
                    "itemWebUrl": f"https://example.com/{item_id}",
                }
            },
        )()


def test_collect_search_enriches_item_details(tmp_path: Path):
    db_path = tmp_path / "vtc.db"
    data_dir = tmp_path / "data"
    database_url = f"sqlite:///{db_path}"
    migrate(database_url)

    sf = make_session_factory(database_url)
    fake = FakeBrowseClient()

    with sf() as s:
        repo = Repo(s)
        count = collect_search(repo, fake, "vintage", limit=2, data_dir=data_dir, enrich_details=True)
        s.commit()

    with sf() as s:
        rows = list(s.scalars(select(Listing).order_by(Listing.ebay_item_id)))

    assert count == 2
    assert fake.detail_calls == 2
    assert rows[0].title.startswith("detail")


def test_collect_search_without_enrichment_uses_summary(tmp_path: Path):
    db_path = tmp_path / "vtc.db"
    data_dir = tmp_path / "data"
    database_url = f"sqlite:///{db_path}"
    migrate(database_url)

    sf = make_session_factory(database_url)
    fake = FakeBrowseClient()

    with sf() as s:
        repo = Repo(s)
        count = collect_search(repo, fake, "vintage", limit=1, data_dir=data_dir, enrich_details=False)
        s.commit()

    with sf() as s:
        rows = list(s.scalars(select(Listing)))

    assert count == 1
    assert fake.detail_calls == 0
    assert rows[0].title == "summary a"
