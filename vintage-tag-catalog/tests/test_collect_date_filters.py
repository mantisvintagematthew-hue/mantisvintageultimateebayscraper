import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.db.migrate import migrate
from app.db.repo import Repo
from app.db.schema import Listing, make_session_factory
from app.pipeline.collect import CollectionOrchestrator


def test_collect_fixture_respects_listing_date_window(tmp_path: Path):
    db_path = tmp_path / "vtc.db"
    data_dir = tmp_path / "data"
    database_url = f"sqlite:///{db_path}"
    migrate(database_url)

    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "itemSummaries": [
                    {
                        "itemId": "v1|old|0",
                        "title": "old",
                        "itemWebUrl": "https://example.com/old",
                        "itemCreationDate": "2023-01-01T00:00:00Z",
                    },
                    {
                        "itemId": "v1|new|0",
                        "title": "new",
                        "itemWebUrl": "https://example.com/new",
                        "itemCreationDate": "2024-01-10T00:00:00Z",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    sf = make_session_factory(database_url)
    with sf() as s:
        repo = Repo(s)
        orchestrator = CollectionOrchestrator(repo, data_dir)
        count = orchestrator.collect_from_fixture(
            fixture,
            listed_after=datetime(2024, 1, 1, tzinfo=timezone.utc),
            listed_before=datetime(2024, 12, 31, tzinfo=timezone.utc),
        )
        s.commit()

    with sf() as s:
        rows = list(s.scalars(select(Listing)).all())

    assert count == 1
    assert len(rows) == 1
    assert rows[0].ebay_item_id == "v1|new|0"
