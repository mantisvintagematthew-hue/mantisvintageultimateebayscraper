from __future__ import annotations

import json
from pathlib import Path

from app.db.repo import Repo
from app.ebay.browse import EbayBrowseClient


MAX_EBAY_PAGE = 200


def collect_search(repo: Repo, browse: EbayBrowseClient, query: str, limit: int, data_dir: Path) -> int:
    """Collect listings from eBay browse API using paginated fetches."""
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    remaining = max(0, limit)
    offset = 0
    count = 0
    while remaining > 0:
        page_size = min(MAX_EBAY_PAGE, remaining)
        result = browse.search(query=query, limit=page_size, offset=offset)
        if not result.items:
            break
        for item in result.items:
            item_id = item["itemId"]
            raw_path = raw_dir / f"{item_id}.json"
            raw_path.write_text(json.dumps(item, indent=2), encoding="utf-8")
            repo.upsert_listing(item, str(raw_path))
            count += 1
            remaining -= 1
            if remaining <= 0:
                break
        offset += len(result.items)
    return count


def collect_from_fixture(repo: Repo, fixture_path: Path, data_dir: Path) -> int:
    """Collect listings using an offline fixture containing eBay Browse response JSON."""
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    items = payload.get("itemSummaries", [])
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for item in items:
        item_id = item["itemId"]
        raw_path = raw_dir / f"{item_id}.json"
        raw_path.write_text(json.dumps(item, indent=2), encoding="utf-8")
        repo.upsert_listing(item, str(raw_path))
        count += 1
    return count
