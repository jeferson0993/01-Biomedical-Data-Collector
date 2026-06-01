from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import CollectionStatus, SourceType


class CollectionCreate(BaseModel):
    source: SourceType
    external_id: str
    params: dict[str, object] | None = None


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    format: str
    file_size: int | None = None
    checksum_sha256: str | None = None
    minio_path: str


class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: SourceType
    external_id: str
    status: CollectionStatus
    raw_path: str | None = None
    metadata_: dict[str, object] | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    datasets: list[DatasetOut] = []


class CollectionListOut(BaseModel):
    items: list[CollectionOut]
    total: int
