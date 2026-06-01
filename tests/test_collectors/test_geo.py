from __future__ import annotations

import httpx
import pytest
import respx
from httpx import Response

from app.collectors.geo.collector import GEOCollector


@pytest.mark.asyncio
async def test_geo_fetch_success() -> None:
    stub_id = "GSE12345"
    fake_content = b"SOFT format data\n"

    with respx.mock:
        route = respx.get(
            "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi",
            params={"acc": stub_id, "targ": "self", "form": "text", "view": "full"},
        )
        route.return_value = Response(200, content=fake_content)

        collector = GEOCollector()
        files = await collector.fetch(stub_id)

    assert len(files) == 1
    data, filename = files[0]
    assert data == fake_content
    assert filename == f"{stub_id}.soft"


@pytest.mark.asyncio
async def test_geo_fetch_http_error() -> None:
    with respx.mock:
        route = respx.get(
            "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi",
            params={"acc": "INVALID", "targ": "self", "form": "text", "view": "full"},
        )
        route.return_value = Response(404)

        collector = GEOCollector()
        with pytest.raises(httpx.HTTPStatusError):
            await collector.fetch("INVALID")
