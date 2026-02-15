from __future__ import annotations

from pathlib import Path
from sqlalchemy import select

from app.db.repo import Repo
from app.db.schema import Image
from app.vision.rank_hero import score_hero_image
from app.vision.rank_tag import score_tag_image


def pick_images(repo: Repo, listings: list, tag_threshold: float = 0.35, hero_threshold: float = 0.35) -> int:
    picked = 0
    for listing in listings:
        images = list(repo.session.scalars(select(Image).where(Image.listing_id == listing.id)))
        if not images:
            continue
        tag_best = max(images, key=lambda im: score_tag_image(Path(im.local_path)))
        hero_best = max(images, key=lambda im: score_hero_image(Path(im.local_path)))
        tag_score = score_tag_image(Path(tag_best.local_path))
        hero_score = score_hero_image(Path(hero_best.local_path))
        repo.set_listing_role_image(listing.id, tag_best.id, "tag", tag_score)
        repo.set_listing_role_image(listing.id, hero_best.id, "hero", hero_score)
        repo.set_needs_review(listing.id, tag_score < tag_threshold or hero_score < hero_threshold)
        picked += 1
    return picked
