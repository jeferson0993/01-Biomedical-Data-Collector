from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.enums import CollectionStatus, SourceType


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[SourceType] = mapped_column(
        SAEnum(SourceType, name="sourcetype"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[CollectionStatus] = mapped_column(
        SAEnum(CollectionStatus, name="collectionstatus"),
        nullable=False,
        default=CollectionStatus.pending,
    )
    raw_path: Mapped[str | None] = mapped_column(nullable=True)
    metadata_: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    datasets: Mapped[list[Dataset]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(nullable=False)
    format: Mapped[str] = mapped_column(nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(nullable=True)
    minio_path: Mapped[str] = mapped_column(nullable=False)

    collection: Mapped[Collection] = relationship(back_populates="datasets")
