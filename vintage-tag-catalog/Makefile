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
