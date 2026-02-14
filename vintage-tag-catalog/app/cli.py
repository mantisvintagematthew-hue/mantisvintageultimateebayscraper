from __future__ import annotations

from pathlib import Path

import typer
from sqlalchemy import select

from app.config import get_settings
from app.db.migrate import migrate
from app.db.repo import Repo
from app.db.schema import Extraction, Listing, make_session_factory
from app.ebay.auth import EbayAuthClient
from app.ebay.browse import EbayBrowseClient
from app.pipeline.collect import collect_search
from app.pipeline.download_images import fetch_images
from app.pipeline.extract_pipeline import export_jsonl, process_listing
from app.pipeline.select_images import pick_images


app = typer.Typer(help="Vintage Tag Catalog CLI")


@app.callback()
def init_db():
    settings = get_settings()
    migrate(settings.database_url)


@app.command("collect")
def collect(query: str, limit: int = 200):
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    auth = EbayAuthClient(settings.ebay_client_id, settings.ebay_client_secret)
    browse = EbayBrowseClient(auth.token(), settings.ebay_marketplace)
    with sf() as s:
        repo = Repo(s)
        count = collect_search(repo, browse, query, limit, settings.data_dir)
        s.commit()
    typer.echo(f"Collected {count} listings")


@app.command("fetch-images")
def fetch_images_cmd(since_hours: int = 24):
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        repo = Repo(s)
        count = fetch_images(repo, repo.recent_listings(since_hours), settings.data_dir)
        s.commit()
    typer.echo(f"Fetched {count} images")


@app.command("pick-images")
def pick_images_cmd(since_hours: int = 24):
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        repo = Repo(s)
        count = pick_images(repo, repo.recent_listings(since_hours))
        s.commit()
    typer.echo(f"Picked tag/hero for {count} listings")


@app.command("extract")
def extract_cmd(since_hours: int = 24):
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
def date_cmd(since_hours: int = 24):
    extract_cmd(since_hours=since_hours)


@app.command("export")
def export_cmd(format: str = "jsonl", out: str = "exports/listings.jsonl"):
    if format != "jsonl":
        raise typer.BadParameter("Only jsonl is currently supported")
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        count = export_jsonl(s, Path(out))
    typer.echo(f"Exported {count} rows to {out}")


if __name__ == "__main__":
    app()
