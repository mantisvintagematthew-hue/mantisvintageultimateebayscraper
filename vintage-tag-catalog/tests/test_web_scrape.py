from pathlib import Path

import pytest

from app.web.scrape import EbayWebCollector, parse_detail_html, parse_search_html


def test_parse_search_html_extracts_items():
    html = (Path(__file__).parent / "fixtures" / "web" / "ebay_search_sample.html").read_text(encoding="utf-8")
    items = parse_search_html(html)
    assert len(items) == 2
    assert items[0].itemId == "web|123456789012|0"
    assert items[1].title == "Single Stitch Rap Tee"


def test_parse_detail_html_extracts_fields():
    html = (Path(__file__).parent / "fixtures" / "web" / "ebay_item_detail_sample.html").read_text(encoding="utf-8")
    detail = parse_detail_html(html)
    assert "made in usa" in (detail["description"] or "").lower()
    assert detail["seller_username"] == "retro_seller"


def test_web_collector_enforces_small_batch_limit():
    collector = EbayWebCollector()
    with pytest.raises(ValueError):
        collector.search(query="vintage tee", limit=80, data_dir=Path("."))
