from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from app.collectors.base import AbstractCollector
from app.collectors.geo.collector import GEOCollector
from app.collectors.ncbi_gene.collector import NCBIGeneCollector
from app.collectors.pubmed.collector import PubMedCollector
from app.collectors.uniprot.collector import UniProtCollector
from app.config import settings
from app.database import async_session
from app.models.collection import Collection, Dataset
from app.models.enums import CollectionStatus
from app.storage.minio_client import MinioClient

logger = logging.getLogger(__name__)

_collector_registry: dict[str, type[AbstractCollector]] = {
    "geo": GEOCollector,
    "ncbi_gene": NCBIGeneCollector,
    "pubmed": PubMedCollector,
    "uniprot": UniProtCollector,
}

minio_client = MinioClient()


def _build_collector(source: str) -> AbstractCollector | None:
    cls = _collector_registry.get(source)
    if cls is None:
        return None
    if source in ("ncbi_gene", "pubmed"):
        return cls.create(api_key=settings.ncbi_api_key, email=settings.ncbi_email)
    return cls.create()


async def run_collection(collection_id: uuid.UUID) -> None:
    logger.info("Starting collection %s", collection_id)
    try:
        async with async_session() as session:
            result = await session.execute(
                select(Collection).where(Collection.id == collection_id)
            )
            collection = result.scalar_one_or_none()
            if collection is None:
                logger.warning("Collection %s not found", collection_id)
                return

            collector = _build_collector(collection.source.value)
            if collector is None:
                collection.status = CollectionStatus.failed
                collection.error_message = f"Unknown source: {collection.source}"
                await session.commit()
                logger.error(
                    "Unknown source %s for collection %s", collection.source, collection_id
                )
                return

            collection.status = CollectionStatus.running
            await session.commit()

            try:
                collect_result = await collector.collect(
                    external_id=collection.external_id,
                    minio_client=minio_client,
                    params=collection.metadata_,
                )
            except Exception as exc:
                collection.status = CollectionStatus.failed
                collection.error_message = str(exc)
                await session.commit()
                logger.exception("Collect failed for %s: %s", collection_id, exc)
                return

            if not collect_result.success:
                collection.status = CollectionStatus.failed
                collection.error_message = collect_result.error_message
                await session.commit()
                logger.error(
                    "Collection %s failed: %s", collection_id, collect_result.error_message
                )
                return

            collection.status = CollectionStatus.completed
            collection.raw_path = f"{collector.source}/{collection.external_id}"
            collection.metadata_ = collect_result.metadata

            for upload in collect_result.uploads:
                dataset = Dataset(
                    collection_id=collection.id,
                    filename=upload.object_name.rsplit("/", 1)[-1],
                    format=upload.object_name.rsplit(".", 1)[-1],
                    minio_path=upload.minio_path,
                )
                session.add(dataset)

            await session.commit()
            logger.info("Collection %s completed successfully", collection_id)
    except Exception:
        logger.exception("Unexpected error in run_collection for %s", collection_id)
