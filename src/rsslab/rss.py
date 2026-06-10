from __future__ import annotations

import httpx


class HttpFetcher:
    def fetch(self, url: str) -> bytes:
        headers = {"User-Agent": "rsslab/0.1 (+https://example.local/rsslab)"}
        with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content
