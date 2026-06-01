from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_session
from app.main import app
from app.models.collection import Collection


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


def _setup_create(mock_session: AsyncMock) -> None:
    """Configure mock_session to handle a create-collection flow."""
    mock_session.add = MagicMock()

    def _refresh(obj: object) -> None:
        if isinstance(obj, Collection):
            now = datetime.now()
            obj.id = uuid.uuid4()
            obj.created_at = now
            obj.updated_at = now

    mock_session.refresh = AsyncMock(side_effect=_refresh)
    mock_session.commit = AsyncMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())


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
