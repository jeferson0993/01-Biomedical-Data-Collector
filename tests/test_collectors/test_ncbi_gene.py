from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.collectors.ncbi_gene.collector import NCBIGeneCollector


@pytest.mark.asyncio
async def test_ncbi_gene_fetch_success() -> None:
    stub_id = "7157"
    summary_xml = b"<summary>p53</summary>"
    full_xml = b"<gene>full p53 data</gene>"

    with respx.mock:
        summary_route = respx.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params={"db": "gene", "id": stub_id},
        )
        summary_route.return_value = Response(200, content=summary_xml)

        efetch_route = respx.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "gene", "id": stub_id, "rettype": "xml"},
        )
        efetch_route.return_value = Response(200, content=full_xml)

        collector = NCBIGeneCollector()
        files = await collector.fetch(stub_id)

    assert len(files) == 2
    assert files[0] == (summary_xml, f"{stub_id}_summary.xml")
    assert files[1] == (full_xml, f"{stub_id}_full.xml")


@pytest.mark.asyncio
async def test_ncbi_gene_fetch_with_api_key() -> None:
    stub_id = "7157"
    with respx.mock:
        summary_route = respx.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params={"db": "gene", "id": stub_id, "api_key": "testkey", "email": "t@t.com"},
        )
        summary_route.return_value = Response(200, content=b"<summary/>")

        efetch_route = respx.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={
                "db": "gene",
                "id": stub_id,
                "rettype": "xml",
                "api_key": "testkey",
                "email": "t@t.com",
            },
        )
        efetch_route.return_value = Response(200, content=b"<full/>")

        collector = NCBIGeneCollector(api_key="testkey", email="t@t.com")
        files = await collector.fetch(stub_id)

    assert len(files) == 2
