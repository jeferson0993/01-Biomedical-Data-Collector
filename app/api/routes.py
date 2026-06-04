from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.collectors.uniprot.collector import UniProtCollector
from app.database import get_session
from app.models.collection import Collection, Dataset
from app.models.enums import CollectionStatus, SourceType
from app.schemas.collection import CollectionCreate, CollectionListOut, CollectionOut
from app.storage.minio_client import MinioClient
from app.tasks import run_collection

router = APIRouter(prefix="/collections", tags=["collections"])

_minio = MinioClient()


@router.post("", response_model=CollectionOut, status_code=201)
async def create_collection(
    body: CollectionCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Collection:
    collection = Collection(
        source=body.source,
        external_id=body.external_id,
        status=CollectionStatus.pending,
        metadata_=body.params,
    )
    session.add(collection)
    await session.commit()
    await session.refresh(collection)

    background_tasks.add_task(run_collection, collection.id)
    return collection


@router.get("", response_model=CollectionListOut)
async def list_collections(
    source: SourceType | None = Query(None),  # noqa: B008
    status: CollectionStatus | None = Query(None),  # noqa: B008
    limit: int = Query(20, ge=1, le=100),  # noqa: B008
    offset: int = Query(0, ge=0),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> dict[str, object]:
    query = select(Collection).options(selectinload(Collection.datasets))
    count_query = select(func.count(Collection.id))

    if source is not None:
        query = query.where(Collection.source == source)
        count_query = count_query.where(Collection.source == source)
    if status is not None:
        query = query.where(Collection.status == status)
        count_query = count_query.where(Collection.status == status)

    query = query.order_by(Collection.created_at.desc()).offset(offset).limit(limit)

    result = await session.execute(query)
    items = list(result.scalars().all())

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    return {"items": items, "total": total}


@router.get("/{collection_id}", response_model=CollectionOut)
async def get_collection(
    collection_id: UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Collection:
    result = await session.execute(
        select(Collection)
        .options(selectinload(Collection.datasets))
        .where(Collection.id == collection_id)
    )
    collection = result.scalar_one_or_none()
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


@router.post("/upload", response_model=CollectionOut, status_code=201)
async def upload_file(
    file: UploadFile = File(...),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Collection:
    data = await file.read()

    collection = Collection(
        source=SourceType.upload,
        external_id=file.filename or "untitled",
        status=CollectionStatus.completed,
    )
    session.add(collection)
    await session.commit()
    await session.refresh(collection)

    object_name = f"upload/{collection.id}/{file.filename}"
    upload_result = await _minio.upload(object_name, data)

    fmt = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "bin"
    dataset = Dataset(
        collection_id=collection.id,
        filename=file.filename or "untitled",
        format=fmt,
        file_size=len(data),
        minio_path=upload_result.minio_path,
    )
    session.add(dataset)
    collection.raw_path = f"upload/{collection.id}"
    await session.commit()
    await session.refresh(collection)

    return collection


@router.get("/{collection_id}/download/{dataset_id}")
async def download_dataset(
    collection_id: UUID,
    dataset_id: UUID,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> Response:
    result = await session.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.collection_id == collection_id)
    )
    dataset = result.scalar_one_or_none()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    prefix = f"{_minio.bucket}/"
    object_name = dataset.minio_path.removeprefix(prefix)
    data = await _minio.download(object_name)

    media_types = {
        "xml": "application/xml",
        "fasta": "text/plain",
        "fa": "text/plain",
        "fastq": "text/plain",
        "fq": "text/plain",
        "txt": "text/plain",
        "json": "application/json",
        "csv": "text/csv",
        "tsv": "text/tab-separated-values",
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gz": "application/gzip",
    }
    media_type = media_types.get(dataset.format, "application/octet-stream")

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{dataset.filename}"'},
    )


@router.post("/uniprot/batch", status_code=200)
async def uniprot_batch(
    accessions: list[str],
) -> dict[str, object]:
    collector = UniProtCollector()
    results: list[dict[str, object]] = []
    for acc in accessions:
        try:
            files = await collector.fetch(acc)
            results.append({
                "accession": acc,
                "success": True,
                "files": [f for _, f in files],
                "error": None,
            })
        except Exception as exc:
            results.append({
                "accession": acc,
                "success": False,
                "files": [],
                "error": str(exc),
            })
    successes = sum(1 for r in results if r["success"])
    return {"results": results, "total": len(results), "success_count": successes}
