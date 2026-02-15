from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from PIL import Image

from app.db.repo import Repo

logger = logging.getLogger(__name__)


@dataclass
class ImageFetchStats:
    attempted: int = 0
    downloaded: int = 0
    failed: int = 0


def fetch_images(repo: Repo, listings: list, data_dir: Path, max_retries: int = 3, backoff_s: float = 0.75) -> ImageFetchStats:
    img_dir = data_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    stats = ImageFetchStats()
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for listing in listings:
            payload = _load_json(Path(listing.raw_json_path))
            urls = _extract_image_urls(payload)
            for url in urls:
                stats.attempted += 1
                content = _fetch_with_retries(client, url, max_retries=max_retries, backoff_s=backoff_s)
                if content is None:
                    stats.failed += 1
                    continue
                sha = hashlib.sha256(content).hexdigest()
                ext = _guess_ext(url)
                local = img_dir / f"{sha}{ext}"
                if not local.exists():
                    local.write_bytes(content)
                width = height = None
                try:
                    with Image.open(local) as im:
                        width, height = im.size
                except Exception:
                    logger.warning("failed to read dimensions for %s", local)
                repo.add_image(listing.id, url, str(local), sha, width, height)
                stats.downloaded += 1
    return stats


def _fetch_with_retries(client: httpx.Client, url: str, max_retries: int, backoff_s: float) -> bytes | None:
    wait = backoff_s
    for attempt in range(max_retries):
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPError as exc:
            if attempt + 1 >= max_retries:
                logger.warning("image fetch failed url=%s err=%s", url, exc)
                return None
            time.sleep(wait)
            wait *= 2
    return None


def _extract_image_urls(payload: dict) -> list[str]:
    urls: list[str] = []
    for key in ["imageUrls"]:
        urls.extend(payload.get(key, []) or [])
    image = payload.get("image") or {}
    if image.get("imageUrl"):
        urls.append(image["imageUrl"])
    for img in payload.get("additionalImages", []) or []:
        if img.get("imageUrl"):
            urls.append(img["imageUrl"])
    return list(dict.fromkeys(urls))


def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _guess_ext(url: str) -> str:
    suffix = Path(url.split("?")[0]).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"
