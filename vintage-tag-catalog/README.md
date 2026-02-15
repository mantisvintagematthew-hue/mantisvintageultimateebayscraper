# vintage-tag-catalog

Local-first pipeline for collecting eBay vintage t-shirt listings, downloading/listing images, selecting tag + hero images, extracting date signals, inferring manufacturing date, resolving canonical date output, and exporting JSONL.

## Stack
- Python 3.11+
- SQLite + SQLAlchemy
- Typer CLI
- httpx for eBay API
- OpenCV + Pillow for image scoring
- EasyOCR for tag OCR

## Quick start

```bash
cd vintage-tag-catalog
cp .env.example .env
make setup
# optional OCR model support
pip install -e .[ocr]
```

Set `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` in `.env`.

## Readiness checks

Run preflight checks before hands-on testing:

```bash
vtc doctor
```

This verifies data directory setup, database connectivity, and eBay credential presence.

## CLI commands

```bash
vtc collect --query "vintage single stitch t shirt" --limit 200
vtc collect --query "vintage single stitch t shirt" --limit 200 --enrich-details true
vtc fetch-images --since-hours 24
vtc pick-images --since-hours 24
vtc extract --since-hours 24
vtc date --since-hours 24
vtc export --format jsonl --out exports/listings.jsonl
```

## Offline fixture workflow

You can run collection without eBay credentials by using a fixture JSON:

```bash
vtc collect --fixture tests/fixtures/ebay_search.json --limit 200
```

This is useful in CI/offline testing and for local iteration on pipeline stages after collection.

## Direct API test-user flow

Use this flow for live end-to-end testing with real eBay API credentials:

```bash
vtc doctor
vtc collect --query "vintage single stitch t shirt" --limit 100 --enrich-details true
vtc fetch-images --since-hours 48
vtc pick-images --since-hours 48
vtc extract --since-hours 48
vtc date --since-hours 48
vtc export --format jsonl --out exports/listings.jsonl
```

## Database schema
Implemented tables:
- `listings`
- `images`
- `listing_images`
- `extractions`
- `date_inference`
- `date_resolution`

## Docker

```bash
docker build -t vtc .
docker run --rm -it --env-file .env -v $(pwd)/data:/app/data vtc --help
```

## Devcontainer
`.devcontainer/devcontainer.json` installs Python dependencies automatically using `pip install -e .[dev]`.

## Tests

```bash
make test
```

Includes:
- declared date extraction tests
- date resolver tests
- image ranker score tests
- offline collect fixture tests
- collect enrichment behavior tests

## Notes
- EasyOCR is used for easier containerization (no system tesseract dependency).
- Image rankers are heuristic v1 implementations and set `needs_review` when confidence is low.
- `collect` retries transient eBay API failures (429/5xx) with short exponential backoff.
