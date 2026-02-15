from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.db.schema import make_session_factory
from app.db.repo import Repo
from app.ebay.auth import EbayAuthClient
from app.ebay.browse import EbayBrowseClient
from app.observability import configure_logging, start_run_id
from app.pipeline.collect import CollectionOrchestrator

app = FastAPI(title="VTC UI")

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.on_event("startup")
def _startup() -> None:
    configure_logging()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return TEMPLATES.TemplateResponse("index.html", {"request": request, "message": None})


@app.post("/collect", response_class=HTMLResponse)
def collect_from_ui(
    request: Request,
    query: str = Form(...),
    mode: str = Form("api"),
    limit: int = Form(50),
    enrich_details: bool = Form(True),
    web_fixture_html: str = Form(""),
    listed_after: str = Form(""),
    listed_before: str = Form(""),
):
    mode = mode.lower()
    if mode == "web" and not (25 <= limit <= 50):
        return TEMPLATES.TemplateResponse(
            "index.html",
            {"request": request, "message": "Web mode requires limit between 25 and 50."},
            status_code=400,
        )
    if mode == "web" and (listed_after.strip() or listed_before.strip()):
        return TEMPLATES.TemplateResponse(
            "index.html",
            {"request": request, "message": "Listing date filters are currently supported in API mode only."},
            status_code=400,
        )

    try:
        parsed_after = _parse_user_datetime(listed_after)
        parsed_before = _parse_user_datetime(listed_before)
    except ValueError:
        return TEMPLATES.TemplateResponse(
            "index.html",
            {"request": request, "message": "Invalid date format. Use ISO date/datetime like 2024-01-01 or 2024-01-01T00:00:00Z."},
            status_code=400,
        )
    if parsed_after and parsed_before and parsed_after > parsed_before:
        return TEMPLATES.TemplateResponse(
            "index.html",
            {"request": request, "message": "listed_after must be <= listed_before."},
            status_code=400,
        )

    run_id = start_run_id()
    settings = get_settings()
    sf = make_session_factory(settings.database_url)
    with sf() as s:
        repo = Repo(s)
        repo.create_collect_run(run_id=run_id, mode=mode, query=query, limit=limit)
        orchestrator = CollectionOrchestrator(repo, settings.data_dir)
        if mode == "api":
            if not settings.ebay_client_id or not settings.ebay_client_secret:
                msg = "Missing EBAY credentials for API mode."
                repo.finish_collect_run(run_id, status="failed", collected_count=0, error_message=msg)
                s.commit()
                return TEMPLATES.TemplateResponse("index.html", {"request": request, "message": msg}, status_code=400)
            auth = EbayAuthClient(settings.ebay_client_id, settings.ebay_client_secret)
            browse = EbayBrowseClient(auth.token(), settings.ebay_marketplace)
            count = orchestrator.collect_api(
                browse,
                query,
                limit,
                enrich_details=enrich_details,
                listed_after=parsed_after,
                listed_before=parsed_before,
            )
        else:
            html_fixture = Path(web_fixture_html) if web_fixture_html else None
            count = orchestrator.collect_web(query, limit, html_fixture=html_fixture)
        repo.finish_collect_run(run_id=run_id, status="completed", collected_count=count)
        s.commit()

    msg = f"Collection complete: {count} listings collected in {mode} mode (run_id={run_id})."
    return TEMPLATES.TemplateResponse("index.html", {"request": request, "message": msg})


def _parse_user_datetime(raw: str) -> datetime | None:
    if not raw or not raw.strip():
        return None
    val = raw.strip()
    if val.endswith("Z"):
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    dt = datetime.fromisoformat(val)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
