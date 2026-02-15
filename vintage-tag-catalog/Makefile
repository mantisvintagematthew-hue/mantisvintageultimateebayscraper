setup:
	python -m pip install -e .[dev]

setup-ocr:
	python -m pip install -e .[ocr]

test:
	pytest -q

doctor:
	vtc doctor --mode all

run-collect-api:
	vtc collect --mode api --query "vintage single stitch t shirt" --limit 50 --enrich-details true

run-collect-web:
	vtc collect --mode web --query "vintage single stitch t shirt" --limit 25

run-collect-web-fixture:
	vtc collect --mode web --query "vintage single stitch t shirt" --limit 25 --web-fixture-html tests/fixtures/web/ebay_search_sample.html

run-collect-offline:
	vtc collect --fixture tests/fixtures/ebay_search.json --limit 50

run-all:
	vtc run-all --mode api --query "vintage single stitch t shirt" --limit 50 --since-hours 72

run-all-web-fixture:
	vtc run-all --mode web --query "vintage single stitch t shirt" --limit 25 --web-fixture-html tests/fixtures/web/ebay_search_sample.html --since-hours 72

run-ui:
	vtc ui --host 127.0.0.1 --port 8080

metrics:
	vtc metrics --out exports/metrics.json

qa-sample:
	vtc qa-sample --sample-size 30 --out exports/qa_sample.jsonl
