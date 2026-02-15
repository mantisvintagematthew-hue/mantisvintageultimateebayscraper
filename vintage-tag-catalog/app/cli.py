from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import typer
import uvicorn
from sqlalchemy import func, select

from app.config import get_settings
from app.db.migrate import migrate
from app.db.repo import Repo
from app.db.schema import DateInference, DateResolution, Extraction, Image, Listing, ListingImage, make_engine, make_session_factory
from app.ebay.auth import EbayAuthClient
from app.ebay.browse import EbayBrowseClient
from app.observability import configure_logging, start_run_id
from app.pipeline.collect import CollectionOrchestrator
from app.pipeline.download_images import fetch_images
from app.pipeline.extract_pipeline import export_jsonl, process_listing
from app.pipeline.metrics import aggregate_db_metrics, write_run_metrics
from app.pipeline.select_images import pick_images
from app.web.scrape import EbayWebCollector


app = typer.Typer(help="Vintage Tag Catalog CLI")
logger = logging.getLogger(__name__)


@app.callback()
def init_db() -> None:
    configure_logging()
    settings = get_settings()
    migrate(settings.database_url)


@app.command("doctor")
def doctor(mode: str = typer.Option("all", help="Check scope: all | api | web")) -> None:
    settings = get_settings()
    mode = mode.lower()
    if mode not in {"all", "api", "web"}:
        raise typer.BadParameter("mode must be one of: all, api, web")

    checks: list[tuple[str, bool, str]] = []
    checks.append(("data_dir_exists", settings.data_dir.exists(), str(settings.data_dir)))
    try:
        engine = make_engine(settings.database_url)
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        checks.append(("database_connectivity", True, settings.database_url))
    except Exception as exc:
        checks.append(("database_connectivity", False, str(exc)))

    if mode in {"all", "api"}:
        has_creds = bool(settings.ebay_client_id and settings.ebay_client_secret)
        checks.append(("api_credentials_present", has_creds, "set EBAY_CLIENT_ID/EBAY_CLIENT_SECRET"))

    if mode in {"all", "web"}:
        try:
            health = EbayWebCollector().check_health()
            checks.append(("web_robots_ok", health["robots_ok"], health.get("detail", "")))
            checks.append(("web_reachability_ok", health["reachability_ok"], health.get("detail", "")))
            checks.append(("web_selectors_ok", health["selectors_ok"], health.get("detail", "")))
        except Exception as exc:
            checks.append(("web_health_check", False, str(exc)))

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
    mode: str = typer.Option("api", help="Collection mode: api | web"),
    fixture: Path | None = typer.Option(None, exists=True, dir_okay=False, help="Offline fixture JSON path"),
    web_fixture_html: Path | None = typer.Option(None, exists=True, dir_okay=False, help="Offline HTML fixture for web mode"),
    enrich_details: bool = typer.Option(True, help="Fetch detailed item payloads via Browse item endpoint"),
    listed_after: str | None = typer.Option(None, help="Optional listing lower bound (ISO date/datetime, e.g. 2024-01-01)"),
    listed_before: str | None = typer.Option(None, help="Optional listing upper bound (ISO date/datetime, e.g. 2024-01-31)"),
) -> None:
    run_id = start_run_id()
    mode = mode.lower()
    if mode not in {"api", "web"}:
        raise typer.BadParameter("mode must be one of: api, web")
    if mode == "web" and not (25 <= limit <= 50):
        raise typer.BadParameter("web mode supports small batches only: limit must be 25-50")
    if mode == "web" and (listed_after or listed_before):
        raise typer.BadParameter("listing date filters are currently supported in API/fixture mode only")

    parsed_listed_after = _parse_user_datetime(listed_after, option_name="listed-after")
    parsed_listed_before = _parse_user_datetime(listed_before, option_name="listed-before")
    if parsed_listed_after and parsed_listed_before and parsed_listed_after > parsed_listed_before:
        raise typer.BadParameter("listed-after must be less than or equal to listed-before")

    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        repo = Repo(s)
        repo.create_collect_run(run_id=run_id, mode=mode if not fixture else "fixture", query=query, limit=limit)
        orchestrator = CollectionOrchestrator(repo, settings.data_dir)
        try:
            if fixture:
                count = orchestrator.collect_from_fixture(
                    fixture,
                    limit=limit,
                    listed_after=parsed_listed_after,
                    listed_before=parsed_listed_before,
                )
                source = f"fixture={fixture}"
            elif mode == "api":
                if not settings.ebay_client_id or not settings.ebay_client_secret:
                    raise typer.BadParameter("Missing eBay credentials. Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET.")
                auth = EbayAuthClient(settings.ebay_client_id, settings.ebay_client_secret)
                browse = EbayBrowseClient(auth.token(), settings.ebay_marketplace)
                count = orchestrator.collect_api(
                    browse,
                    query,
                    limit,
                    enrich_details=enrich_details,
                    listed_after=parsed_listed_after,
                    listed_before=parsed_listed_before,
                )
                source = "ebay_api"
            else:
                count = orchestrator.collect_web(query=query, limit=limit, html_fixture=web_fixture_html)
                source = "ebay_web"
            repo.finish_collect_run(run_id=run_id, status="completed", collected_count=count)
        except Exception as exc:
            repo.finish_collect_run(run_id=run_id, status="failed", collected_count=0, error_message=str(exc))
            s.commit()
            typer.echo(f"Collection failed: {exc}")
            raise typer.Exit(code=1)
        finally:
            s.commit()

    logger.info("collect complete source=%s count=%s mode=%s", source, count, mode)
    write_run_metrics(settings.data_dir, run_id, {"stage": "collect", "source": source, "mode": mode, "count": count})
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
    mode: str = typer.Option("api", help="Collection mode: api | web"),
    fixture: Path | None = typer.Option(None, exists=True, dir_okay=False, help="Offline fixture JSON path"),
    web_fixture_html: Path | None = typer.Option(None, exists=True, dir_okay=False, help="Offline HTML fixture for web mode"),
    listed_after: str | None = typer.Option(None, help="Optional listing lower bound (ISO date/datetime)"),
    listed_before: str | None = typer.Option(None, help="Optional listing upper bound (ISO date/datetime)"),
) -> None:
    run_id = start_run_id()
    collect(
        query=query,
        limit=limit,
        mode=mode,
        fixture=fixture,
        web_fixture_html=web_fixture_html,
        enrich_details=True,
        listed_after=listed_after,
        listed_before=listed_before,
    )
    fetch_images_cmd(since_hours=since_hours)
    pick_images_cmd(since_hours=since_hours)
    date_cmd(since_hours=since_hours)

    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        summary = aggregate_db_metrics(s)
    write_run_metrics(settings.data_dir, run_id, {"stage": "run-all", "mode": mode, **summary})
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
                    "source_mode": listing.source_mode,
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


@app.command("ui")
def ui_cmd(host: str = "127.0.0.1", port: int = 8080) -> None:
    uvicorn.run("app.ui.server:app", host=host, port=port, reload=False)


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


def _parse_user_datetime(raw: str | None, option_name: str) -> datetime | None:
    if not raw:
        return None
    val = raw.strip()
    try:
        if val.endswith("Z"):
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(val)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        raise typer.BadParameter(f"invalid --{option_name} datetime: {raw}") from None


if __name__ == "__main__":
    app()
