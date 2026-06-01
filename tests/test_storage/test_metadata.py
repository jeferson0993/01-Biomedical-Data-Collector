from __future__ import annotations

import json
from datetime import UTC, datetime

from app.storage.metadata import build_metadata


def test_build_metadata_defaults() -> None:
    meta = build_metadata(source="geo")
    assert meta["source"] == "geo"
    assert meta["version"] == "unknown"
    assert meta["parameters"] == {}
    assert isinstance(meta["date"], str)
    # verify ISO format
    datetime.fromisoformat(meta["date"])


def test_build_metadata_with_version() -> None:
    meta = build_metadata(source="uniprot", source_version="2025_01")
    assert meta["version"] == "2025_01"


def test_build_metadata_with_params() -> None:
    meta = build_metadata(source="pubmed", parameters={"query": "cancer"})
    assert meta["parameters"] == {"query": "cancer"}


def test_build_metadata_json_serializable() -> None:
    meta = build_metadata(source="ncbi_gene", source_version="1.0")
    json.dumps(meta)  # should not raise


def test_build_metadata_date_is_utc() -> None:
    meta = build_metadata(source="geo")
    dt = datetime.fromisoformat(meta["date"])
    assert dt.tzinfo is not None
    assert dt.tzinfo.utcoffset(dt) == UTC.utcoffset(dt)
