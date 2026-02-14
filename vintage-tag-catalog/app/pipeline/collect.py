from __future__ import annotations

import json
from pathlib import Path

from app.db.repo import Repo
from app.ebay.browse import EbayBrowseClient


def collect_search(repo: Repo, browse: EbayBrowseClient, query: str, limit: int, data_dir: Path) -> int:
    result = browse.search(query=query, limit=limit)
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for item in result.items:
        item_id = item["itemId"]
        raw_path = raw_dir / f"{item_id}.json"
        raw_path.write_text(json.dumps(item, indent=2), encoding="utf-8")
        repo.upsert_listing(item, str(raw_path))
        count += 1
    return count
