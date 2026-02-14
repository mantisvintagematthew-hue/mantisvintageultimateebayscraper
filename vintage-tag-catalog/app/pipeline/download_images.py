from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
from PIL import Image

from app.db.repo import Repo


def fetch_images(repo: Repo, listings: list, data_dir: Path) -> int:
    img_dir = data_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    with httpx.Client(timeout=60) as client:
        for listing in listings:
            payload = _load_json(Path(listing.raw_json_path))
            for url in payload.get("imageUrls", []) or _extract_image_urls(payload):
                content = client.get(url).content
                sha = hashlib.sha256(content).hexdigest()
                ext = ".jpg"
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
    urls = []
    if payload.get("image") and payload["image"].get("imageUrl"):
        urls.append(payload["image"]["imageUrl"])
    for img in payload.get("additionalImages", []):
        if img.get("imageUrl"):
            urls.append(img["imageUrl"])
    return urls


def _load_json(path: Path) -> dict:
    import json

    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}
