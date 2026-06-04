from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks import run_collection


def _make_async_session(mock_session: AsyncMock) -> MagicMock:
    """Wrap mock_session so that 'async with async_session() as session' works."""
    cm = MagicMock()
    cm.__aenter__.return_value = mock_session
    cm.__aexit__.return_value = None
    return cm


@pytest.mark.asyncio
async def test_run_collection_success() -> None:
    collection_id = uuid.uuid4()
    mock_collection = MagicMock()
    mock_collection.id = collection_id
    mock_collection.source = MagicMock()
    mock_collection.source.value = "geo"
    mock_collection.external_id = "GSE123"
    mock_collection.metadata_ = {}

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_collection
    mock_session.execute.return_value = mock_result

    mock_upload = MagicMock()
    mock_upload.object_name = "geo/GSE123/file.soft"
    mock_upload.minio_path = "raw/geo/GSE123/file.soft"
    mock_upload.checksum_sha256 = "abc"
    mock_upload.tags = {}
    mock_collect_result = MagicMock()
    mock_collect_result.success = True
    mock_collect_result.error_message = None
    mock_collect_result.uploads = [mock_upload]
    mock_collect_result.metadata = {"source": "geo"}

    with (
        patch("app.tasks.async_session", return_value=_make_async_session(mock_session)),
        patch("app.tasks._build_collector") as mock_build,
        patch("app.tasks.minio_client"),
    ):
        mock_collector = MagicMock()
        mock_collector.source = "geo"
        mock_collector.collect = AsyncMock(return_value=mock_collect_result)
        mock_build.return_value = mock_collector

        await run_collection(collection_id)

    assert mock_collection.status.value == "completed"
    assert mock_collection.raw_path == "geo/GSE123"


@pytest.mark.asyncio
async def test_run_collection_unknown_source() -> None:
    collection_id = uuid.uuid4()
    mock_collection = MagicMock()
    mock_collection.id = collection_id
    mock_collection.source = MagicMock()
    mock_collection.source.value = "invalid_source"

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_collection
    mock_session.execute.return_value = mock_result

    with (
        patch("app.tasks.async_session", return_value=_make_async_session(mock_session)),
        patch("app.tasks._build_collector", return_value=None),
    ):
        await run_collection(collection_id)

    assert mock_collection.status.value == "failed"


@pytest.mark.asyncio
async def test_run_collection_fetch_fails() -> None:
    collection_id = uuid.uuid4()
    mock_collection = MagicMock()
    mock_collection.id = collection_id
    mock_collection.source = MagicMock()
    mock_collection.source.value = "geo"
    mock_collection.external_id = "BAD"
    mock_collection.metadata_ = {}

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_collection
    mock_session.execute.return_value = mock_result

    mock_collect_result = MagicMock()
    mock_collect_result.success = False
    mock_collect_result.error_message = "Fetch error"

    with (
        patch("app.tasks.async_session", return_value=_make_async_session(mock_session)),
        patch("app.tasks._build_collector") as mock_build,
        patch("app.tasks.minio_client"),
    ):
        mock_collector = MagicMock()
        mock_collector.collect = AsyncMock(return_value=mock_collect_result)
        mock_build.return_value = mock_collector

        await run_collection(collection_id)

    assert mock_collection.status.value == "failed"
    assert mock_collection.error_message == "Fetch error"
