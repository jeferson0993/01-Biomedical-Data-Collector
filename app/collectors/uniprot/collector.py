from __future__ import annotations

import httpx

from app.collectors.base import AbstractCollector

_client = httpx.AsyncClient()


class UniProtCollector(AbstractCollector):
    source = "uniprot"

    def __init__(
        self,
        base_url: str = "https://rest.uniprot.org",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__()
        self._base_url = base_url
        self._client = client or _client

    async def fetch(
        self, external_id: str, _params: dict[str, object] | None = None
    ) -> list[tuple[bytes, str]]:
        await self._wait_for_slot()
        url = f"{self._base_url}/uniprotkb/{external_id}"
        headers = {"Accept": "text/xml"}
        response = await self._client.get(url, headers=headers)
        response.raise_for_status()

        await self._wait_for_slot()
        fasta_url = f"{self._base_url}/uniprotkb/{external_id}.fasta"
        fasta_response = await self._client.get(fasta_url)
        fasta_response.raise_for_status()

        files: list[tuple[bytes, str]] = [
            (response.content, f"{external_id}.xml"),
            (fasta_response.content, f"{external_id}.fasta"),
        ]
        return files
