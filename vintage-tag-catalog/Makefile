setup:
	python -m pip install -e .[dev]

test:
	pytest -q

run-collect:
	vtc collect --query "vintage single stitch t shirt" --limit 50

run-collect-offline:
	vtc collect --fixture tests/fixtures/ebay_search.json --limit 50
