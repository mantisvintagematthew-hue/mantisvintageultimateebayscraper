from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select

from app.db.schema import DateResolution, Extraction, Listing



def write_run_metrics(data_dir: Path, run_id: str, metrics: dict) -> Path:
    runs_dir = data_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{run_id}.json"
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return path



def aggregate_db_metrics(session) -> dict:
    total = session.scalar(select(func.count()).select_from(Listing)) or 0
    needs_review = session.scalar(select(func.count()).select_from(Listing).where(Listing.needs_review.is_(True))) or 0
    resolved = session.scalar(select(func.count()).select_from(DateResolution)) or 0
    conflicts = session.scalar(select(func.count()).select_from(DateResolution).where(DateResolution.conflict_flag.is_(True))) or 0
    extracted = session.scalar(select(func.count()).select_from(Extraction)) or 0
    return {
        "total_listings": int(total),
        "needs_review_count": int(needs_review),
        "needs_review_rate": (needs_review / total) if total else 0.0,
        "resolution_count": int(resolved),
        "conflict_count": int(conflicts),
        "conflict_rate": (conflicts / resolved) if resolved else 0.0,
        "extraction_count": int(extracted),
    }
