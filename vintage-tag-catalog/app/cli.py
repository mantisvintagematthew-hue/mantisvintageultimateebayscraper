from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
from sqlalchemy import func, select

from app.config import get_settings
from app.db.migrate import migrate
from app.db.repo import Repo
from app.db.schema import DateInference, DateResolution, Extraction, Image, Listing, ListingImage, make_engine, make_session_factory
from app.ebay.auth import EbayAuthClient
from app.ebay.browse import EbayBrowseClient
from app.observability import configure_logging, start_run_id
from app.pipeline.collect import collect_from_fixture, collect_search
from app.pipeline.download_images import fetch_images
from app.pipeline.extract_pipeline import export_jsonl, process_listing
from app.pipeline.metrics import aggregate_db_metrics, write_run_metrics
from app.pipeline.select_images import pick_images


app = typer.Typer(help="Vintage Tag Catalog CLI")
logger = logging.getLogger(__name__)


@app.callback()
def init_db() -> None:
    configure_logging()
    settings = get_settings()
    migrate(settings.database_url)


@app.command("doctor")
def doctor() -> None:
    """Basic readiness checks for local test users before running pipeline."""
    settings = get_settings()
    checks: list[tuple[str, bool, str]] = []
    checks.append(("data_dir_exists", settings.data_dir.exists(), str(settings.data_dir)))
    try:
        engine = make_engine(settings.database_url)
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        checks.append(("database_connectivity", True, settings.database_url))
    except Exception as exc:
        checks.append(("database_connectivity", False, str(exc)))

    has_creds = bool(settings.ebay_client_id and settings.ebay_client_secret)
    checks.append(("ebay_credentials_present", has_creds, "set EBAY_CLIENT_ID/EBAY_CLIENT_SECRET"))

    failures = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        marker = "✅" if ok else "❌"
        typer.echo(f"{marker} {name}: {detail}")

    if failures:
        raise typer.Exit(code=1)


@app.command("collect")
def collect(
    query: str = typer.Option("vintage single stitch t shirt", help="Search query"),
    limit: int = typer.Option(200, help="Max listings to collect"),
    fixture: Path | None = typer.Option(None, exists=True, dir_okay=False, help="Offline fixture JSON path"),
    enrich_details: bool = typer.Option(True, help="Fetch detailed item payloads via Browse item endpoint"),
) -> None:
    run_id = start_run_id()
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        repo = Repo(s)
        if fixture:
            count = collect_from_fixture(repo, fixture, settings.data_dir, limit=limit)
            source = f"fixture={fixture}"
        else:
            if not settings.ebay_client_id or not settings.ebay_client_secret:
                raise typer.BadParameter("Missing eBay credentials. Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET.")
            auth = EbayAuthClient(settings.ebay_client_id, settings.ebay_client_secret)
            browse = EbayBrowseClient(auth.token(), settings.ebay_marketplace)
            count = collect_search(repo, browse, query, limit, settings.data_dir, enrich_details=enrich_details)
            source = "ebay_api"
        s.commit()
    logger.info("collect complete source=%s count=%s", source, count)
    write_run_metrics(settings.data_dir, run_id, {"stage": "collect", "source": source, "count": count})
    typer.echo(f"Collected {count} listings from {source} (run_id={run_id})")


@app.command("fetch-images")
def fetch_images_cmd(since_hours: int = 24) -> None:
    run_id = start_run_id()
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        repo = Repo(s)
        stats = fetch_images(repo, repo.recent_listings(since_hours), settings.data_dir)
        s.commit()
    metrics = {"stage": "fetch-images", "attempted": stats.attempted, "downloaded": stats.downloaded, "failed": stats.failed}
    write_run_metrics(settings.data_dir, run_id, metrics)
    typer.echo(f"Fetched {stats.downloaded} images (attempted={stats.attempted}, failed={stats.failed}, run_id={run_id})")


@app.command("pick-images")
def pick_images_cmd(since_hours: int = 24) -> None:
    run_id = start_run_id()
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        repo = Repo(s)
        count = pick_images(repo, repo.recent_listings(since_hours))
        s.commit()
    write_run_metrics(settings.data_dir, run_id, {"stage": "pick-images", "count": count})
    typer.echo(f"Picked tag/hero for {count} listings (run_id={run_id})")


@app.command("extract")
def extract_cmd(since_hours: int = 24) -> None:
    run_id = start_run_id()
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        repo = Repo(s)
        listings = repo.recent_listings(since_hours)
        for listing in listings:
            process_listing(repo, listing)
        s.commit()
    write_run_metrics(settings.data_dir, run_id, {"stage": "extract", "count": len(listings)})
    typer.echo(f"Extracted for {len(listings)} listings (run_id={run_id})")


@app.command("date")
def date_cmd(since_hours: int = 24) -> None:
    extract_cmd(since_hours=since_hours)


@app.command("run-all")
def run_all(
    query: str = typer.Option("vintage single stitch t shirt", help="Search query"),
    limit: int = typer.Option(100, help="Max listings to collect"),
    since_hours: int = typer.Option(72, help="Window for downstream stages"),
    fixture: Path | None = typer.Option(None, exists=True, dir_okay=False, help="Offline fixture JSON path"),
) -> None:
    """Convenience command for direct tester end-to-end runs."""
    run_id = start_run_id()
    collect(query=query, limit=limit, fixture=fixture, enrich_details=True)
    fetch_images_cmd(since_hours=since_hours)
    pick_images_cmd(since_hours=since_hours)
    date_cmd(since_hours=since_hours)

    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        summary = aggregate_db_metrics(s)
    write_run_metrics(settings.data_dir, run_id, {"stage": "run-all", **summary})
    typer.echo(f"Run-all complete (run_id={run_id})")


@app.command("metrics")
def metrics_cmd(out: str | None = None) -> None:
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        summary = aggregate_db_metrics(s)
    if out:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    typer.echo(json.dumps(summary, indent=2))


@app.command("qa-sample")
def qa_sample(sample_size: int = 30, out: str = "exports/qa_sample.jsonl") -> None:
    """Generate a manual QA sample for reviewers (tag/hero/date validation)."""
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with sf() as s:
        rows = s.execute(
            select(Listing, Extraction, DateInference, DateResolution)
            .join(Extraction, Listing.id == Extraction.listing_id, isouter=True)
            .join(DateInference, Listing.id == DateInference.listing_id, isouter=True)
            .join(DateResolution, Listing.id == DateResolution.listing_id, isouter=True)
            .order_by(func.random())
            .limit(sample_size)
        ).all()

        with out_path.open("w", encoding="utf-8") as f:
            for listing, extraction, inferred, resolved in rows:
                tag_row = s.scalar(select(ListingImage).where(ListingImage.listing_id == listing.id, ListingImage.role == "tag"))
                hero_row = s.scalar(select(ListingImage).where(ListingImage.listing_id == listing.id, ListingImage.role == "hero"))
                tag_img = s.get(Image, tag_row.image_id) if tag_row else None
                hero_img = s.get(Image, hero_row.image_id) if hero_row else None
                item = {
                    "listing_id": listing.id,
                    "ebay_item_id": listing.ebay_item_id,
                    "title": listing.title,
                    "needs_review": listing.needs_review,
                    "tag_image_path": tag_img.local_path if tag_img else None,
                    "hero_image_path": hero_img.local_path if hero_img else None,
                    "declared": _obj_public(extraction),
                    "inferred": _obj_public(inferred),
                    "resolved": _obj_public(resolved),
                }
                f.write(json.dumps(item) + "\n")

    typer.echo(f"Wrote QA sample: {out_path}")


@app.command("export")
def export_cmd(format: str = "jsonl", out: str = "exports/listings.jsonl") -> None:
    if format != "jsonl":
        raise typer.BadParameter("Only jsonl is currently supported")
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        count = export_jsonl(s, Path(out))
    typer.echo(f"Exported {count} rows to {out}")



def _obj_public(obj):
    if obj is None:
        return None
    return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}


if __name__ == "__main__":
    app()
