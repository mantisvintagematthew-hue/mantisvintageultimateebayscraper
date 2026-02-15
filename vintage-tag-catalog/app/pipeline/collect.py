from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import httpx

from app.db.repo import Repo
from app.ebay.browse import EbayBrowseClient
from app.web.scrape import EbayWebCollector


MAX_EBAY_PAGE = 200
logger = logging.getLogger(__name__)


class CollectionOrchestrator:
    def __init__(self, repo: Repo, data_dir: Path):
        self.repo = repo
        self.data_dir = data_dir

    def collect_api(
        self,
        browse: EbayBrowseClient,
        query: str,
        limit: int,
        enrich_details: bool = True,
        listed_after: datetime | None = None,
        listed_before: datetime | None = None,
    ) -> int:
        raw_dir = self.data_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        filter_expr = _build_api_filter_expr(listed_after, listed_before)
        remaining = max(0, limit)
        offset = 0
        count = 0
        while remaining > 0:
            page_size = min(MAX_EBAY_PAGE, remaining)
            result = browse.search(query=query, limit=page_size, offset=offset, filter_expr=filter_expr)
            if not result.items:
                break
            for summary in result.items:
                listing_payload = summary
                if enrich_details:
                    try:
                        listing_payload = browse.get_item(summary["itemId"]).item
                    except httpx.HTTPError as exc:
                        logger.warning("detail fetch failed for %s: %s", summary.get("itemId"), exc)
                        listing_payload = summary

                if not _in_listing_date_range(listing_payload, listed_after=listed_after, listed_before=listed_before):
                    continue

                self._persist_payload(listing_payload, source_mode="api")
                count += 1
                remaining -= 1
                if remaining <= 0:
                    break
            offset += len(result.items)
        return count

    def collect_web(self, query: str, limit: int, html_fixture: Path | None = None) -> int:
        collector = EbayWebCollector()
        if html_fixture:
            payloads = collector.search_from_html_fixture(html_fixture, limit=limit, data_dir=self.data_dir)
        else:
            payloads = collector.search(query=query, limit=limit, data_dir=self.data_dir)
        count = 0
        for payload in payloads:
            self._persist_payload(payload, source_mode="web")
            count += 1
        return count

    def collect_from_fixture(
        self,
        fixture_path: Path,
        limit: int | None = None,
        listed_after: datetime | None = None,
        listed_before: datetime | None = None,
    ) -> int:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        items = payload.get("itemSummaries", [])
        if limit is not None and limit <= 0:
            return 0
        count = 0
        for item in items:
            if not _in_listing_date_range(item, listed_after=listed_after, listed_before=listed_before):
                continue
            self._persist_payload(item, source_mode="fixture")
            count += 1
            if limit is not None and limit >= 0 and count >= limit:
                break
        return count

    def _persist_payload(self, listing_payload: dict, source_mode: str) -> None:
        raw_dir = self.data_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        item_id = listing_payload["itemId"]
        raw_path = raw_dir / f"{item_id}.json"
        raw_path.write_text(json.dumps(listing_payload, indent=2), encoding="utf-8")
        self.repo.upsert_listing(listing_payload, str(raw_path), source_mode=source_mode)


# backward-compatible helper functions

def collect_search(repo: Repo, browse: EbayBrowseClient, query: str, limit: int, data_dir: Path, enrich_details: bool = True) -> int:
    return CollectionOrchestrator(repo, data_dir).collect_api(browse, query, limit, enrich_details=enrich_details)


def collect_web_search(repo: Repo, query: str, limit: int, data_dir: Path, html_fixture: Path | None = None) -> int:
    return CollectionOrchestrator(repo, data_dir).collect_web(query, limit, html_fixture=html_fixture)


def collect_from_fixture(repo: Repo, fixture_path: Path, data_dir: Path, limit: int | None = None) -> int:
    return CollectionOrchestrator(repo, data_dir).collect_from_fixture(fixture_path, limit)


def _build_api_filter_expr(listed_after: datetime | None, listed_before: datetime | None) -> str | None:
    if not listed_after and not listed_before:
        return None
    lower = listed_after.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if listed_after else ".."
    upper = listed_before.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if listed_before else ".."
    return f"itemCreationDate:[{lower}..{upper}]"


def _in_listing_date_range(
    listing_payload: dict,
    listed_after: datetime | None,
    listed_before: datetime | None,
) -> bool:
    if not listed_after and not listed_before:
        return True
    listing_dt = _extract_listing_datetime(listing_payload)
    if listing_dt is None:
        return False
    if listed_after and listing_dt < listed_after:
        return False
    if listed_before and listing_dt > listed_before:
        return False
    return True


def _extract_listing_datetime(payload: dict) -> datetime | None:
    for key in ("itemCreationDate", "itemOriginDate", "listingDate", "startDate"):
        raw = payload.get(key)
        dt = _parse_ebay_datetime(raw)
        if dt:
            return dt
    return None


def _parse_ebay_datetime(raw: str | None) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    try:
        if raw.endswith("Z"):
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
