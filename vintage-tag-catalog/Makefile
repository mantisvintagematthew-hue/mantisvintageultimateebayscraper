setup:
	python -m pip install -e .[dev]

test:
	pytest -q

doctor:
	vtc doctor

run-collect:
	vtc collect --query "vintage single stitch t shirt" --limit 50 --enrich-details true

run-collect-offline:
	vtc collect --fixture tests/fixtures/ebay_search.json --limit 50

run-all:
	vtc run-all --query "vintage single stitch t shirt" --limit 50 --since-hours 72

metrics:
	vtc metrics --out exports/metrics.json

qa-sample:
	vtc qa-sample --sample-size 30 --out exports/qa_sample.jsonl
