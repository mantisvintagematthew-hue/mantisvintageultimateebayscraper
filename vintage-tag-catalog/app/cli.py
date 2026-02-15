from __future__ import annotations

from pathlib import Path

import typer

from app.config import get_settings
from app.db.migrate import migrate
from app.db.repo import Repo
from app.db.schema import make_session_factory
from app.ebay.auth import EbayAuthClient
from app.ebay.browse import EbayBrowseClient
from app.pipeline.collect import collect_from_fixture, collect_search
from app.pipeline.download_images import fetch_images
from app.pipeline.extract_pipeline import export_jsonl, process_listing
from app.pipeline.select_images import pick_images


app = typer.Typer(help="Vintage Tag Catalog CLI")


@app.callback()
def init_db() -> None:
    settings = get_settings()
    migrate(settings.database_url)


@app.command("collect")
def collect(
    query: str = typer.Option("vintage single stitch t shirt", help="Search query"),
    limit: int = typer.Option(200, help="Max listings to collect"),
    fixture: Path | None = typer.Option(None, exists=True, dir_okay=False, help="Offline fixture JSON path"),
) -> None:
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        repo = Repo(s)
        if fixture:
            count = collect_from_fixture(repo, fixture, settings.data_dir)
            source = f"fixture={fixture}"
        else:
            auth = EbayAuthClient(settings.ebay_client_id, settings.ebay_client_secret)
            browse = EbayBrowseClient(auth.token(), settings.ebay_marketplace)
            count = collect_search(repo, browse, query, limit, settings.data_dir)
            source = "ebay_api"
        s.commit()
    typer.echo(f"Collected {count} listings from {source}")


@app.command("fetch-images")
def fetch_images_cmd(since_hours: int = 24) -> None:
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        repo = Repo(s)
        count = fetch_images(repo, repo.recent_listings(since_hours), settings.data_dir)
        s.commit()
    typer.echo(f"Fetched {count} images")


@app.command("pick-images")
def pick_images_cmd(since_hours: int = 24) -> None:
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        repo = Repo(s)
        count = pick_images(repo, repo.recent_listings(since_hours))
        s.commit()
    typer.echo(f"Picked tag/hero for {count} listings")


@app.command("extract")
def extract_cmd(since_hours: int = 24) -> None:
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        repo = Repo(s)
        listings = repo.recent_listings(since_hours)
        for listing in listings:
            process_listing(repo, listing)
        s.commit()
    typer.echo(f"Extracted for {len(listings)} listings")


@app.command("date")
def date_cmd(since_hours: int = 24) -> None:
    extract_cmd(since_hours=since_hours)


@app.command("export")
def export_cmd(format: str = "jsonl", out: str = "exports/listings.jsonl") -> None:
    if format != "jsonl":
        raise typer.BadParameter("Only jsonl is currently supported")
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        count = export_jsonl(s, Path(out))
    typer.echo(f"Exported {count} rows to {out}")


if __name__ == "__main__":
    app()
