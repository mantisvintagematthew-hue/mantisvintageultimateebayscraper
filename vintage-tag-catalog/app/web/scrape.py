from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]


@dataclass
class ScrapedItem:
    itemId: str
    itemWebUrl: str
    title: str
    price: dict | None = None
    image: dict | None = None
    seller: dict | None = None
    itemLocation: dict | None = None
    description: str | None = None


class EbayWebCollector:
    def __init__(self, timeout_s: int = 30):
        self.timeout_s = timeout_s

    def search(self, query: str, limit: int, data_dir: Path) -> list[dict]:
        if limit < 1:
            return []
        if limit > 50:
            raise ValueError("Web scraping mode supports batches of 1-50 listings only")

        url = f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(query)}"
        html = self._request_with_backoff(url)
        items = parse_search_html(html)
        payloads = [item.__dict__ for item in items[:limit]]

        raw_dir = data_dir / "raw_web"
        raw_dir.mkdir(parents=True, exist_ok=True)
        snapshot = raw_dir / f"search_{int(time.time())}.json"
        snapshot.write_text(json.dumps(payloads, indent=2), encoding="utf-8")
        return payloads

    def search_from_html_fixture(self, html_path: Path, limit: int, data_dir: Path) -> list[dict]:
        if limit < 1:
            return []
        if limit > 50:
            raise ValueError("Web scraping mode supports batches of 1-50 listings only")
        html = html_path.read_text(encoding="utf-8")
        items = parse_search_html(html)
        payloads = [item.__dict__ for item in items[:limit]]

        raw_dir = data_dir / "raw_web"
        raw_dir.mkdir(parents=True, exist_ok=True)
        snapshot = raw_dir / f"search_fixture_{int(time.time())}.json"
        snapshot.write_text(json.dumps(payloads, indent=2), encoding="utf-8")
        return payloads

    def check_health(self, query: str = "vintage single stitch t shirt") -> dict:
        robots_url = "https://www.ebay.com/robots.txt"
        search_url = f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(query)}"

        robots_ok = False
        search_ok = False
        selectors_ok = False
        detail = ""

        try:
            robots_txt = self._request_with_backoff(robots_url)
            robots_ok = "user-agent" in robots_txt.lower()
        except Exception as exc:
            detail = f"robots_error={exc}"

        try:
            html = self._request_with_backoff(search_url)
            search_ok = True
            selectors_ok = len(parse_search_html(html)) > 0
            if not selectors_ok and not detail:
                detail = "search_selectors_empty"
        except Exception as exc:
            if not detail:
                detail = f"search_error={exc}"

        return {
            "robots_ok": robots_ok,
            "reachability_ok": search_ok,
            "selectors_ok": selectors_ok,
            "ok": robots_ok and search_ok and selectors_ok,
            "detail": detail,
        }

    def _request_with_backoff(self, url: str, max_retries: int = 3, backoff_s: float = 1.0) -> str:
        wait = backoff_s
        for attempt in range(max_retries):
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            with httpx.Client(timeout=self.timeout_s, follow_redirects=True, headers=headers) as client:
                resp = client.get(url)
            if resp.status_code in {429, 500, 502, 503, 504} and attempt + 1 < max_retries:
                time.sleep(wait)
                wait *= 2
                continue
            resp.raise_for_status()
            body = resp.text
            if "captcha" in body.lower() or "puzzle" in body.lower():
                raise RuntimeError("Detected anti-bot challenge page from eBay")
            return body
        raise RuntimeError("web request failed after retries")


def parse_search_html(html: str) -> list[ScrapedItem]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[ScrapedItem] = []
    for li in soup.select("li.s-item"):
        link = li.select_one("a.s-item__link")
        title_el = li.select_one("div.s-item__title, h3.s-item__title")
        price_el = li.select_one("span.s-item__price")
        image_el = li.select_one("img.s-item__image-img")

        if not link or not title_el:
            continue
        href = link.get("href", "")
        item_id = _extract_item_id(href)
        if not item_id:
            continue

        rows.append(
            ScrapedItem(
                itemId=item_id,
                itemWebUrl=href,
                title=title_el.get_text(strip=True),
                price={"value": _extract_price(price_el.get_text(strip=True)) if price_el else None, "currency": "USD"},
                image={"imageUrl": image_el.get("src") if image_el else None},
            )
        )
    return rows


def parse_detail_html(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    desc = soup.select_one("div#desc_div, div.x-item-description-child, div.d-item-description")
    seller = soup.select_one("span.mbg-nw, div.ux-seller-section__item--seller a")
    location = soup.select_one("div.ux-labels-values__values-content span.ux-textspans")
    return {
        "description": desc.get_text(" ", strip=True) if desc else None,
        "seller_username": seller.get_text(strip=True) if seller else None,
        "location": location.get_text(strip=True) if location else None,
    }


def _extract_item_id(url: str) -> str:
    marker = "/itm/"
    if marker not in url:
        return ""
    tail = url.split(marker, 1)[1]
    segment = tail.split("?", 1)[0]
    m = re.search(r"(\d{9,15})", segment)
    digits = m.group(1) if m else ""
    return f"web|{digits}|0" if digits else ""


def _extract_price(raw: str) -> str | None:
    filtered = "".join(ch for ch in raw if ch.isdigit() or ch in ".,")
    return filtered.replace(",", "") if filtered else None
