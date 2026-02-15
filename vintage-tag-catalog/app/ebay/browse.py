from __future__ import annotations

import time

import httpx

from app.ebay.models import EbayItemDetailResult, EbaySearchResult


class EbayBrowseClient:
    def __init__(self, token: str, marketplace: str = "EBAY_US"):
        self.token = token
        self.marketplace = marketplace

    def search(
        self,
        query: str,
        limit: int = 200,
        offset: int = 0,
        filter_expr: str | None = None,
    ) -> EbaySearchResult:
        params = {"q": query, "limit": min(limit, 200), "offset": offset}
        if filter_expr:
            params["filter"] = filter_expr
        payload = self._request_json(
            "https://api.ebay.com/buy/browse/v1/item_summary/search",
            params=params,
        )
        return EbaySearchResult(items=payload.get("itemSummaries", []), raw=payload)

    def get_item(self, item_id: str) -> EbayItemDetailResult:
        payload = self._request_json(f"https://api.ebay.com/buy/browse/v1/item/{item_id}")
        return EbayItemDetailResult(item=payload)

    def _request_json(self, url: str, params: dict | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
        }
        backoff_s = 1.0
        for attempt in range(3):
            with httpx.Client(timeout=30) as client:
                resp = client.get(url, params=params, headers=headers)
            if resp.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                time.sleep(backoff_s)
                backoff_s *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("Unreachable request retry branch")
