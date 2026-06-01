from __future__ import annotations

import httpx
import pytest
import respx
from httpx import Response

from app.collectors.pubmed.collector import PubMedCollector


@pytest.mark.asyncio
async def test_pubmed_fetch_success() -> None:
    stub_id = "12345678"
    summary_xml = b"<PubmedArticleSet><summary/></PubmedArticleSet>"
    full_xml = b"<PubmedArticleSet><full/></PubmedArticleSet>"

    with respx.mock:
        esummary_route = respx.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params={"db": "pubmed", "id": stub_id},
        )
        esummary_route.return_value = Response(200, content=summary_xml)

        efetch_route = respx.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "pubmed", "id": stub_id, "rettype": "xml"},
        )
        efetch_route.return_value = Response(200, content=full_xml)

        collector = PubMedCollector()
        files = await collector.fetch(stub_id)

    assert len(files) == 2
    assert files[0] == (summary_xml, f"{stub_id}_summary.xml")
    assert files[1] == (full_xml, f"{stub_id}_full.xml")


@pytest.mark.asyncio
async def test_pubmed_fetch_http_error() -> None:
    with respx.mock:
        route = respx.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params={"db": "pubmed", "id": "0"},
        )
        route.return_value = Response(500)

        collector = PubMedCollector()
        with pytest.raises(httpx.HTTPStatusError):
            await collector.fetch("0")
