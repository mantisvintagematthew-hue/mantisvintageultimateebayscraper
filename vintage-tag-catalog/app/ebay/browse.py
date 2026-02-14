from __future__ import annotations

import httpx

from app.ebay.models import EbaySearchResult


class EbayBrowseClient:
    def __init__(self, token: str, marketplace: str = "EBAY_US"):
        self.token = token
        self.marketplace = marketplace

    def search(self, query: str, limit: int = 200, offset: int = 0) -> EbaySearchResult:
        url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                url,
                params={"q": query, "limit": min(limit, 200), "offset": offset},
                headers={"Authorization": f"Bearer {self.token}", "X-EBAY-C-MARKETPLACE-ID": self.marketplace},
            )
            resp.raise_for_status()
            payload = resp.json()
        return EbaySearchResult(items=payload.get("itemSummaries", []), raw=payload)
