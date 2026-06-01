from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from minio import Minio
from minio.error import S3Error

from app.storage.minio_client import MinioClient, UploadResult


def _make_s3error() -> S3Error:
    response = MagicMock(spec=object)
    return S3Error(response, "NoSuchKey", "not found", resource="", request_id="", host_id="")


def test_upload_result_dataclass() -> None:
    result = UploadResult(
        minio_path="raw/test/file.txt",
        bucket="raw",
        object_name="test/file.txt",
        etag="abc123",
        version_id=None,
    )
    assert result.minio_path == "raw/test/file.txt"
    assert result.bucket == "raw"
    assert result.object_name == "test/file.txt"
    assert result.etag == "abc123"
    assert result.version_id is None


@patch("app.storage.minio_client.Minio", return_value=MagicMock(spec=Minio))
def test_minio_client_initialization(_mock_minio: MagicMock) -> None:
    client = MinioClient()
    _mock_minio.assert_called_once()
    assert client.bucket is not None


@pytest.mark.asyncio
@patch("app.storage.minio_client.Minio", return_value=MagicMock(spec=Minio))
async def test_object_exists_true(_mock_minio: MagicMock) -> None:
    client = MinioClient()
    exists = await client.object_exists("some/path.txt")
    assert exists is True


@pytest.mark.asyncio
@patch("app.storage.minio_client.Minio", return_value=MagicMock(spec=Minio))
async def test_object_exists_false(_mock_minio: MagicMock) -> None:
    client = MinioClient()
    client.client.stat_object = MagicMock(side_effect=_make_s3error())
    exists = await client.object_exists("missing.txt")
    assert exists is False
