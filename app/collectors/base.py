from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Self

from app.storage.metadata import build_metadata
from app.storage.minio_client import MinioClient, UploadResult


@dataclass
class CollectResult:
    external_id: str
    source: str
    success: bool
    uploads: list[UploadResult] = field(default_factory=list)
    error_message: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class AbstractCollector(ABC):
    source: str = ""

    @classmethod
    def create(cls, **kwargs: object) -> Self:
        return cls(**kwargs)

    @abstractmethod
    async def fetch(
        self, external_id: str, params: dict[str, object] | None = None
    ) -> list[tuple[bytes, str]]:
        ...

    async def validate(self, data: bytes, _filename: str) -> bool:
        return len(data) > 0

    async def collect(
        self,
        external_id: str,
        minio_client: MinioClient,
        params: dict[str, object] | None = None,
    ) -> CollectResult:
        try:
            files = await self.fetch(external_id, params=params)
        except Exception as exc:
            return CollectResult(
                external_id=external_id,
                source=self.source,
                success=False,
                error_message=str(exc),
                metadata=build_metadata(self.source),
            )

        uploads: list[UploadResult] = []
        uploaded_objects: list[str] = []
        for data, filename in files:
            if not await self.validate(data, filename):
                for obj in uploaded_objects:
                    await minio_client.delete(obj)
                return CollectResult(
                    external_id=external_id,
                    source=self.source,
                    success=False,
                    error_message=f"Validation failed for {filename}",
                    metadata=build_metadata(self.source),
                )
            object_name = f"{self.source}/{external_id}/{filename}"
            upload = await minio_client.upload(object_name, data)
            uploads.append(upload)
            uploaded_objects.append(object_name)

        meta = build_metadata(
            self.source,
            parameters=params or {},
        )
        meta_bytes = json.dumps(meta, indent=2).encode()
        object_name = f"{self.source}/{external_id}/metadata.json"
        await minio_client.upload(object_name, meta_bytes, content_type="application/json")

        return CollectResult(
            external_id=external_id,
            source=self.source,
            success=True,
            uploads=uploads,
            metadata=meta,
        )
