from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Self

from app.config import settings
from app.storage.metadata import build_metadata
from app.storage.minio_client import MinioClient, UploadResult
from app.utils.retry import retry_async

logger = logging.getLogger(__name__)


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

    def __init__(self) -> None:
        self._rate_semaphore = asyncio.Semaphore(settings.rate_limit_max_calls)
        self._rate_period = settings.rate_limit_period_seconds
        self._last_request: float = 0.0

    async def _wait_for_slot(self) -> None:
        async with self._rate_semaphore:
            elapsed = time.monotonic() - self._last_request
            if elapsed < self._rate_period:
                await asyncio.sleep(self._rate_period - elapsed)
            self._last_request = time.monotonic()

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
            files = await retry_async(
                self.fetch, external_id, params=params,
                max_retries=3, base_delay=1.0, max_delay=30.0,
            )
        except Exception as exc:
            logger.exception("Fetch failed for %s/%s: %s", self.source, external_id, exc)
            return CollectResult(
                external_id=external_id,
                source=self.source,
                success=False,
                error_message=str(exc),
                metadata=build_metadata(self.source),
            )

        uploads: list[UploadResult] = []
        uploaded_objects: list[str] = []
        obj_tags = {"source": self.source, "external_id": external_id}
        for data, filename in files:
            if not await self.validate(data, filename):
                for obj in uploaded_objects:
                    await minio_client.delete(obj)
                logger.warning(
                    "Validation failed for %s/%s/%s", self.source, external_id, filename
                )
                return CollectResult(
                    external_id=external_id,
                    source=self.source,
                    success=False,
                    error_message=f"Validation failed for {filename}",
                    metadata=build_metadata(self.source),
                )
            object_name = f"{self.source}/{external_id}/{filename}"
            upload = await minio_client.upload(object_name, data, tags=obj_tags)
            uploads.append(upload)
            uploaded_objects.append(object_name)

        checksums = [
            {"filename": u.object_name, "sha256": u.checksum_sha256} for u in uploads
        ]
        meta = build_metadata(
            self.source,
            parameters=params or {},
            checksums=checksums,
        )
        meta_bytes = json.dumps(meta, indent=2).encode()
        meta_name = f"{self.source}/{external_id}/metadata.json"
        await minio_client.upload(
            meta_name, meta_bytes, content_type="application/json", tags=obj_tags
        )

        logger.info(
            "Collection %s/%s completed: %d files", self.source, external_id, len(uploads)
        )
        return CollectResult(
            external_id=external_id,
            source=self.source,
            success=True,
            uploads=uploads,
            metadata=meta,
        )
