# vintage-tag-catalog

Local-first pipeline for collecting eBay vintage t-shirt listings, downloading/listing images, selecting tag + hero images, extracting date signals, inferring manufacturing date, resolving canonical date output, and exporting JSONL.

## Stack
- Python 3.11+
- SQLite + SQLAlchemy
- Typer CLI
- FastAPI + Jinja2 (simple operator UI)
- httpx for eBay API and web requests
- OpenCV + Pillow for image scoring
- EasyOCR for tag OCR

## Quick start

```bash
cd vintage-tag-catalog
cp .env.example .env
make setup
# optional OCR model support
make setup-ocr
```

Set `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` in `.env` for API mode.

### Dev container

This repo includes `.devcontainer/devcontainer.json` for reproducible setup. It installs `.[dev,ocr]` automatically so `pytest` and OCR-backed extraction can run immediately inside the container.

## Collection modes

The app supports two collection modes:

1. **API mode** (`--mode api`) — primary mode, uses official eBay API.
2. **Web mode** (`--mode web`) — secondary mode, scrapes eBay search pages in **small batches (25–50)**.

## Readiness checks

```bash
vtc doctor --mode all
vtc doctor --mode api
vtc doctor --mode web
```

- API doctor checks credentials + DB/data setup.
- Web doctor checks robots reachability and selector health.

## CLI commands

```bash
vtc collect --mode api --query "vintage single stitch t shirt" --limit 200
vtc collect --mode api --query "vintage single stitch t shirt" --limit 200 --listed-after 2024-01-01 --listed-before 2024-01-31
vtc collect --mode web --query "vintage single stitch t shirt" --limit 25
vtc collect --mode web --query "vintage single stitch t shirt" --limit 25 --web-fixture-html tests/fixtures/web/ebay_search_sample.html
vtc collect --fixture tests/fixtures/ebay_search.json --limit 200

vtc run-all --mode api --query "vintage single stitch t shirt" --limit 100 --listed-after 2024-01-01 --since-hours 72
vtc run-all --mode web --query "vintage single stitch t shirt" --limit 25 --since-hours 72
vtc run-all --mode web --query "vintage single stitch t shirt" --limit 25 --web-fixture-html tests/fixtures/web/ebay_search_sample.html --since-hours 72

vtc metrics --out exports/metrics.json
vtc qa-sample --sample-size 30 --out exports/qa_sample.jsonl
```

## Frontend UI with mode toggle

Run UI:

```bash
vtc ui --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080` and use the **Mode** dropdown to toggle API/Web collection modes.
Use the **Dark mode** toggle in the top-right to switch themes (preference is saved locally).
You can also set optional listing date bounds (`listed_after`, `listed_before`) in the UI for API collection runs.

## Easy launch (double-click)

- macOS: double-click `Launch_VTC_UI.command`
- Linux: double-click `launch_vtc_ui.sh` (or run `./launch_vtc_ui.sh`)

Both launch scripts start the UI at `http://127.0.0.1:8080`.

## Human-testing (scraper-first) recommendation

If you do not have API keys yet, use this first-round flow:

```bash
vtc doctor --mode web
vtc collect --mode web --query "vintage single stitch t shirt" --limit 25
vtc fetch-images --since-hours 24
vtc pick-images --since-hours 24
vtc date --since-hours 24
vtc metrics --out exports/metrics.json
vtc qa-sample --sample-size 30 --out exports/qa_sample.jsonl
```

## Ready-for-testing checklist

Run this once after cloning:

```bash
make setup
make test
vtc doctor --mode all
```

Then run one end-to-end offline lane:

```bash
vtc run-all --mode web --query "vintage single stitch t shirt" --limit 25 --web-fixture-html tests/fixtures/web/ebay_search_sample.html --since-hours 72
```

If your network blocks direct web requests (403/proxy), use fixture-backed web mode for local pipeline QA:

```bash
vtc run-all --mode web --query "vintage single stitch t shirt" --limit 25 --web-fixture-html tests/fixtures/web/ebay_search_sample.html --since-hours 72
```

## Database schema
Implemented tables:
- `listings` (includes `source_mode`)
- `collect_runs`
- `images`
- `listing_images`
- `extractions`
- `date_inference`
- `date_resolution`

## Acceptance criteria checklist

- API mode behavior remains consistent with previous implementation.
- Web mode runs successfully for 25–50 listings per run.
- UI mode toggle routes collection through selected mode.
- Metrics and QA sampling continue to work post-collection in both modes.

## Notes
- EasyOCR is used for easier containerization (no system tesseract dependency).
- Web mode is intentionally small-batch to reduce anti-bot risk and stabilize first-round human testing.

### Date-bound collection filters

To avoid re-processing older inventory, API and fixture collection support optional bounds:

- `--listed-after` (inclusive lower bound)
- `--listed-before` (inclusive upper bound)

Use ISO values like `2024-01-01` or `2024-01-01T00:00:00Z`.

> Note: web scraping mode does not currently expose reliable listing timestamps from search HTML, so date bounds are rejected in web mode.
