from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from minio import Minio
from minio.error import S3Error

from app.storage.minio_client import MinioClient


def _make_s3error() -> S3Error:
    response = MagicMock(spec=object)
    return S3Error(response, "NoSuchKey", "not found", resource="", request_id="", host_id="")


@pytest.mark.asyncio
@patch("app.storage.minio_client.Minio", return_value=MagicMock(spec=Minio))
async def test_download(_mock_minio: MagicMock) -> None:
    client = MinioClient()
    mock_response = MagicMock()
    mock_response.read.return_value = b"hello world"
    client.client.get_object.return_value = mock_response

    data = await client.download("test/file.txt")

    assert data == b"hello world"
    client.client.get_object.assert_called_once_with("raw", "test/file.txt")
    mock_response.close.assert_called_once()
    mock_response.release_conn.assert_called_once()


@pytest.mark.asyncio
@patch("app.storage.minio_client.Minio", return_value=MagicMock(spec=Minio))
async def test_set_tags(_mock_minio: MagicMock) -> None:
    client = MinioClient()
    await client.set_tags("test/file.txt", {"source": "geo", "key": "val"})

    client.client.set_object_tags.assert_called_once()
    args = client.client.set_object_tags.call_args
    assert args[0][0] == "raw"
    assert args[0][1] == "test/file.txt"
    tags_arg = args[0][2]
    assert tags_arg["source"] == "geo"
    assert tags_arg["key"] == "val"


@pytest.mark.asyncio
@patch("app.storage.minio_client.Minio", return_value=MagicMock(spec=Minio))
async def test_upload_with_tags(_mock_minio: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.etag = "etag123"
    mock_result.version_id = "v1"
    client = MinioClient()
    client.client.put_object.return_value = mock_result

    result = await client.upload("test/file.txt", b"hello", tags={"source": "geo"})

    assert result.checksum_sha256 != ""
    assert result.etag == "etag123"
    assert result.tags == {"source": "geo"}
    client.client.put_object.assert_called_once()
    client.client.set_object_tags.assert_called_once()


@pytest.mark.asyncio
@patch("app.storage.minio_client.Minio", return_value=MagicMock(spec=Minio))
async def test_object_info_found(_mock_minio: MagicMock) -> None:
    mock_stat = MagicMock()
    mock_stat.etag = '"abc123"'
    mock_stat.size = 42
    mock_stat.last_modified = datetime(2025, 1, 1, tzinfo=UTC)
    mock_stat.content_type = "text/plain"
    client = MinioClient()
    client.client.stat_object.return_value = mock_stat

    info = await client.object_info("test/file.txt")

    assert info is not None
    assert info["etag"] == '"abc123"'
    assert info["size"] == 42
    assert info["content_type"] == "text/plain"


@pytest.mark.asyncio
@patch("app.storage.minio_client.Minio", return_value=MagicMock(spec=Minio))
async def test_object_info_not_found(_mock_minio: MagicMock) -> None:
    client = MinioClient()
    client.client.stat_object.side_effect = _make_s3error()

    info = await client.object_info("missing.txt")

    assert info is None


@pytest.mark.asyncio
@patch("app.storage.minio_client.Minio", return_value=MagicMock(spec=Minio))
async def test_list_objects(_mock_minio: MagicMock) -> None:
    mock_obj1 = MagicMock()
    mock_obj1.object_name = "geo/GSE123/file.txt"
    mock_obj1.etag = '"a"'
    mock_obj1.size = 10
    mock_obj1.last_modified = datetime(2025, 1, 1, tzinfo=UTC)

    client = MinioClient()
    client.client.list_objects.return_value = [mock_obj1]

    items = await client.list_objects(prefix="geo/")

    assert len(items) == 1
    assert items[0]["object_name"] == "geo/GSE123/file.txt"
    assert items[0]["etag"] == '"a"'
    client.client.list_objects.assert_called_once()


@pytest.mark.asyncio
@patch("app.storage.minio_client.Minio", return_value=MagicMock(spec=Minio))
async def test_object_exists_cache(_mock_minio: MagicMock) -> None:
    client = MinioClient()

    exists1 = await client.object_exists("cached/path.txt")
    assert exists1 is True
    assert client.client.stat_object.call_count == 1

    exists2 = await client.object_exists("cached/path.txt")
    assert exists2 is True
    assert client.client.stat_object.call_count == 1

    client._exists_cache.pop("cached/path.txt", None)
    exists3 = await client.object_exists("cached/path.txt")
    assert exists3 is True
    assert client.client.stat_object.call_count == 2
