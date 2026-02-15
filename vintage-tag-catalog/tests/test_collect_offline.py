from pathlib import Path

from app.db.migrate import migrate
from app.db.repo import Repo
from sqlalchemy import select

from app.db.schema import Listing, make_session_factory
from app.pipeline.collect import collect_from_fixture


def test_collect_from_fixture(tmp_path: Path):
    db_path = tmp_path / "vtc.db"
    data_dir = tmp_path / "data"
    fixture_path = Path(__file__).parent / "fixtures" / "ebay_search.json"

    database_url = f"sqlite:///{db_path}"
    migrate(database_url)
    sf = make_session_factory(database_url)

    with sf() as s:
        repo = Repo(s)
        count = collect_from_fixture(repo, fixture_path, data_dir)
        s.commit()

    with sf() as s:
        rows = list(s.scalars(select(Listing)))

    assert count == 1
    assert len(rows) == 1
    assert rows[0].ebay_item_id == "v1|1234567890|0"


def test_collect_from_fixture_honors_limit(tmp_path: Path):
    db_path = tmp_path / "vtc.db"
    data_dir = tmp_path / "data"
    fixture_path = Path(__file__).parent / "fixtures" / "ebay_search.json"

    database_url = f"sqlite:///{db_path}"
    migrate(database_url)
    sf = make_session_factory(database_url)

    with sf() as s:
        repo = Repo(s)
        count = collect_from_fixture(repo, fixture_path, data_dir, limit=0)
        s.commit()

    with sf() as s:
        rows = list(s.scalars(select(Listing)))

    assert count == 0
    assert len(rows) == 0
