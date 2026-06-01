from __future__ import annotations

import httpx
import pytest
import respx
from httpx import Response

from app.collectors.uniprot.collector import UniProtCollector


@pytest.mark.asyncio
async def test_uniprot_fetch_success() -> None:
    stub_id = "P04637"
    xml_content = b"<uniprot>p53</uniprot>"
    fasta_content = b">sp|P04637|p53\nsequence\n"

    with respx.mock:
        xml_route = respx.get(
            "https://rest.uniprot.org/uniprotkb/P04637",
            headers={"Accept": "text/xml"},
        )
        xml_route.return_value = Response(200, content=xml_content)

        fasta_route = respx.get(
            "https://rest.uniprot.org/uniprotkb/P04637.fasta",
        )
        fasta_route.return_value = Response(200, content=fasta_content)

        collector = UniProtCollector()
        files = await collector.fetch(stub_id)

    assert len(files) == 2
    assert files[0] == (xml_content, f"{stub_id}.xml")
    assert files[1] == (fasta_content, f"{stub_id}.fasta")


@pytest.mark.asyncio
async def test_uniprot_fetch_not_found() -> None:
    with respx.mock:
        xml_route = respx.get(
            "https://rest.uniprot.org/uniprotkb/NOTEXIST",
            headers={"Accept": "text/xml"},
        )
        xml_route.return_value = Response(404)

        collector = UniProtCollector()
        with pytest.raises(httpx.HTTPStatusError):
            await collector.fetch("NOTEXIST")
