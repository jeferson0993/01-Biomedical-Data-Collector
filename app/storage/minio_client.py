from __future__ import annotations

import asyncio
import hashlib
import io
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, TypeVar

from minio import Minio
from minio.commonconfig import Tags
from minio.error import S3Error

from app.config import settings

T = TypeVar("T")

ObjectInfo = dict[str, object]  # etag, size, last_modified, etc.


@dataclass
class UploadResult:
    minio_path: str
    bucket: str
    object_name: str
    etag: str | None
    version_id: str | None
    checksum_sha256: str = ""
    tags: dict[str, str] = field(default_factory=dict)


class MinioClient:
    def __init__(self) -> None:
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket
        self._exists_cache: dict[str, bool] = {}
        self._stat_cache: dict[str, ObjectInfo] = {}

    def _invalidate(self, object_name: str) -> None:
        self._exists_cache.pop(object_name, None)
        self._stat_cache.pop(object_name, None)

    async def _run(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def ensure_bucket(self) -> None:
        bucket_exists = await self._run(self.client.bucket_exists, self.bucket)
        if not bucket_exists:
            await self._run(self.client.make_bucket, self.bucket)

    async def set_tags(
        self,
        object_name: str,
        tags: dict[str, str],
    ) -> None:
        minio_tags = Tags.new_object_tags()
        for k, v in tags.items():
            minio_tags[k] = v
        await self._run(
            self.client.set_object_tags,
            self.bucket,
            object_name,
            minio_tags,
        )

    async def upload(
        self,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        tags: dict[str, str] | None = None,
    ) -> UploadResult:
        from minio.helpers import ObjectWriteResult

        await self.ensure_bucket()
        checksum = hashlib.sha256(data).hexdigest()
        result: ObjectWriteResult = await self._run(
            self.client.put_object,
            bucket_name=self.bucket,
            object_name=object_name,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        if tags:
            await self.set_tags(object_name, tags)
        self._invalidate(object_name)
        return UploadResult(
            minio_path=f"{self.bucket}/{object_name}",
            bucket=self.bucket,
            object_name=object_name,
            etag=result.etag,
            version_id=result.version_id,
            checksum_sha256=checksum,
            tags=tags or {},
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
        cached = self._exists_cache.get(object_name)
        if cached is not None:
            return cached
        try:
            await self._run(self.client.stat_object, self.bucket, object_name)
            self._exists_cache[object_name] = True
            return True
        except S3Error:
            self._exists_cache[object_name] = False
            return False

    async def object_info(self, object_name: str) -> ObjectInfo | None:
        cached = self._stat_cache.get(object_name)
        if cached is not None:
            return cached
        try:
            obj = await self._run(self.client.stat_object, self.bucket, object_name)
            info: ObjectInfo = {
                "etag": obj.etag,
                "size": obj.size,
                "last_modified": obj.last_modified.isoformat() if obj.last_modified else "",
                "content_type": obj.content_type or "",
            }
            self._stat_cache[object_name] = info
            return info
        except S3Error:
            return None

    async def list_objects(
        self,
        prefix: str = "",
        max_keys: int = 100,
    ) -> list[ObjectInfo]:
        objects = await self._run(
            self.client.list_objects,
            self.bucket,
            prefix=prefix,
            max_keys=max_keys,
            include_user_meta=True,
        )
        result: list[ObjectInfo] = []
        for obj in objects:
            info: ObjectInfo = {
                "object_name": obj.object_name,
                "etag": obj.etag,
                "size": obj.size,
                "last_modified": obj.last_modified.isoformat() if obj.last_modified else "",
            }
            result.append(info)
        return result

    async def delete(self, object_name: str) -> None:
        await self._run(self.client.remove_object, self.bucket, object_name)
        self._invalidate(object_name)
