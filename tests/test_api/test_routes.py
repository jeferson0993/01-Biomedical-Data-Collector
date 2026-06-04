from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_session
from app.main import app
from app.models.collection import Collection, Dataset


@pytest.fixture(autouse=True)
def no_background_task() -> None:
    with patch("app.api.routes.run_collection"):
        yield


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture(autouse=True)
def override_get_session(mock_session: AsyncMock) -> None:
    async def _mock_get_session() -> AsyncMock:
        yield mock_session

    app.dependency_overrides[get_session] = _mock_get_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_uniprot_batch() -> None:
    from app.collectors.uniprot.collector import UniProtCollector

    async def _mock_fetch(acc: str, _params: object = None) -> list[tuple[bytes, str]]:
        if acc == "BAD":
            raise ValueError("not found")
        return [(b"data", f"{acc}.xml"), (b"fasta", f"{acc}.fasta")]

    with patch.object(UniProtCollector, "fetch", side_effect=_mock_fetch):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/collections/uniprot/batch", json=["P12345", "BAD"])

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["success_count"] == 1
    assert data["results"][0]["success"] is True
    assert data["results"][1]["success"] is False


def _setup_create(mock_session: AsyncMock) -> None:
    """Configure mock_session to handle a create-collection flow."""
    created_col: Collection | None = None

    def _add(obj: object) -> None:
        nonlocal created_col
        if isinstance(obj, Collection):
            created_col = obj

    mock_session.add = MagicMock(side_effect=_add)
    mock_session.commit = AsyncMock()

    def _refresh(obj: object) -> None:
        if isinstance(obj, Collection) and obj.id is None:
            now = datetime.now()
            obj.id = uuid.uuid4()
            obj.created_at = now
            obj.updated_at = now

    mock_session.refresh = AsyncMock(side_effect=_refresh)

    async def _execute(_stmt: object) -> MagicMock:
        result = MagicMock()
        if created_col:
            now = datetime.now()
            created_col.id = uuid.uuid4()
            created_col.created_at = now
            created_col.updated_at = now
        result.scalar_one.return_value = created_col
        return result

    mock_session.execute = AsyncMock(side_effect=_execute)


@pytest.mark.asyncio
async def test_create_collection(mock_session: AsyncMock) -> None:
    _setup_create(mock_session)
    payload = {"source": "geo", "external_id": "GSE12345"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/collections", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "geo"
    assert data["external_id"] == "GSE12345"
    assert data["status"] == "pending"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_collections_empty(mock_session: AsyncMock) -> None:
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 0
    mock_session.execute.side_effect = [mock_result, mock_count_result]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/collections")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_get_collection_not_found(mock_session: AsyncMock) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/collections/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_collection_db_call(mock_session: AsyncMock) -> None:
    _setup_create(mock_session)
    payload = {"source": "pubmed", "external_id": "12345678"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/collections", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "pubmed"
    assert data["status"] == "pending"
    assert data["external_id"] == "12345678"
    assert "id" in data


@patch("app.api.routes._minio.upload")
@pytest.mark.asyncio
async def test_upload_file(
    mock_upload: AsyncMock,
    mock_session: AsyncMock,
) -> None:
    _setup_create(mock_session)
    mock_upload.return_value = MagicMock(
        minio_path="raw/upload/uid/file.txt",
        checksum_sha256="abc",
        tags={},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/collections/upload",
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "upload"


@pytest.mark.asyncio
async def test_download_dataset_not_found(mock_session: AsyncMock) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/collections/00000000-0000-0000-0000-000000000000/download/"
            "00000000-0000-0000-0000-000000000000"
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_dataset_success(
    mock_session: AsyncMock,
) -> None:
    dataset_id = uuid.uuid4()
    mock_dataset = MagicMock(spec=Dataset)
    mock_dataset.id = dataset_id
    mock_dataset.filename = "test.txt"
    mock_dataset.format = "txt"
    mock_dataset.minio_path = "test_bucket/geo/GSE123/file.txt"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_dataset
    mock_session.execute.return_value = mock_result

    mock_minio_response = MagicMock()
    mock_minio_response.read.return_value = b"file content"

    with patch("app.api.routes._minio") as mock_minio:
        mock_minio.bucket = "test_bucket"
        mock_minio.download = AsyncMock(return_value=b"file content")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                f"/collections/00000000-0000-0000-0000-000000000000/download/{dataset_id}"
            )

    assert response.status_code == 200
    assert response.content == b"file content"
    assert "attachment" in response.headers["content-disposition"]
