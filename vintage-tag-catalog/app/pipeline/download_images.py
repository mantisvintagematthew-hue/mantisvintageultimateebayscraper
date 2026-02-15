from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
from PIL import Image

from app.db.repo import Repo


def fetch_images(repo: Repo, listings: list, data_dir: Path) -> int:
    img_dir = data_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for listing in listings:
            payload = _load_json(Path(listing.raw_json_path))
            urls = _extract_image_urls(payload)
            for url in urls:
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                except httpx.HTTPError:
                    continue
                content = resp.content
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
                    pass
                repo.add_image(listing.id, url, str(local), sha, width, height)
                downloaded += 1
    return downloaded


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
    # Preserve order while deduping.
    return list(dict.fromkeys(urls))


def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _guess_ext(url: str) -> str:
    suffix = Path(url.split("?")[0]).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"
