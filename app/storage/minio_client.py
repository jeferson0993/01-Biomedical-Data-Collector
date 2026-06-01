from __future__ import annotations

import asyncio
import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, TypeVar

from minio import Minio
from minio.error import S3Error

from app.config import settings

T = TypeVar("T")


@dataclass
class UploadResult:
    minio_path: str
    bucket: str
    object_name: str
    etag: str | None
    version_id: str | None


class MinioClient:
    def __init__(self) -> None:
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket

    async def _run(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def ensure_bucket(self) -> None:
        bucket_exists = await self._run(self.client.bucket_exists, self.bucket)
        if not bucket_exists:
            await self._run(self.client.make_bucket, self.bucket)

    async def upload(
        self,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> UploadResult:
        from minio.helpers import ObjectWriteResult

        result: ObjectWriteResult = await self._run(
            self.client.put_object,
            bucket_name=self.bucket,
            object_name=object_name,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return UploadResult(
            minio_path=f"{self.bucket}/{object_name}",
            bucket=self.bucket,
            object_name=object_name,
            etag=result.etag,
            version_id=result.version_id,
        )

    async def download(self, object_name: str) -> bytes:
        response = await self._run(self.client.get_object, self.bucket, object_name)
        try:
            data: bytes = response.read()
            return data
        finally:
            response.close()
            response.release_conn()

    async def presigned_url(
        self, object_name: str, expires: timedelta = timedelta(hours=1)
    ) -> str:
        return await self._run(
            self.client.presigned_get_object,
            self.bucket,
            object_name,
            expires=expires,
        )

    async def object_exists(self, object_name: str) -> bool:
        try:
            await self._run(self.client.stat_object, self.bucket, object_name)
            return True
        except S3Error:
            return False

    async def delete(self, object_name: str) -> None:
        await self._run(self.client.remove_object, self.bucket, object_name)
