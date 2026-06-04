from __future__ import annotations

import httpx

from app.collectors.base import AbstractCollector

_client = httpx.AsyncClient()


class PubMedCollector(AbstractCollector):
    source = "pubmed"

    BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(
        self,
        api_key: str = "",
        email: str = "",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__()
        self._api_key = api_key
        self._email = email
        self._client = client or _client

    def _common_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self._api_key:
            params["api_key"] = self._api_key
        if self._email:
            params["email"] = self._email
        return params

    async def fetch(
        self, external_id: str, _params: dict[str, object] | None = None
    ) -> list[tuple[bytes, str]]:
        common = self._common_params()

        esummary_params = {"db": "pubmed", "id": external_id, **common}
        await self._wait_for_slot()
        response = await self._client.get(
            f"{self.BASE}/esummary.fcgi",
            params=esummary_params,
        )
        response.raise_for_status()
        summary_bytes = response.content

        efetch_params = {"db": "pubmed", "id": external_id, "rettype": "xml", **common}
        await self._wait_for_slot()
        response_full = await self._client.get(
            f"{self.BASE}/efetch.fcgi",
            params=efetch_params,
        )
        response_full.raise_for_status()
        full_bytes = response_full.content

        files: list[tuple[bytes, str]] = [
            (summary_bytes, f"{external_id}_summary.xml"),
            (full_bytes, f"{external_id}_full.xml"),
        ]
        return files
