from __future__ import annotations

import base64
import time
import httpx


class EbayAuthClient:
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None
        self._exp: float = 0

    def token(self) -> str:
        if self._token and time.time() < self._exp - 60:
            return self._token
        creds = f"{self.client_id}:{self.client_secret}".encode()
        auth = base64.b64encode(creds).decode()
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                "https://api.ebay.com/identity/v1/oauth2/token",
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"},
            )
            resp.raise_for_status()
            payload = resp.json()
        self._token = payload["access_token"]
        self._exp = time.time() + int(payload.get("expires_in", 7200))
        return self._token
