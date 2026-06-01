from __future__ import annotations

import httpx

from app.collectors.base import AbstractCollector

_client = httpx.AsyncClient()


class GEOCollector(AbstractCollector):
    source = "geo"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or _client

    async def fetch(
        self, external_id: str, _params: dict[str, object] | None = None
    ) -> list[tuple[bytes, str]]:
        url = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi"
        query_params: dict[str, str] = {
            "acc": external_id,
            "targ": "self",
            "form": "text",
            "view": "full",
        }
        response = await self._client.get(url, params=query_params, follow_redirects=True)
        response.raise_for_status()
        content = response.content
        filename = f"{external_id}.soft"
        return [(content, filename)]
