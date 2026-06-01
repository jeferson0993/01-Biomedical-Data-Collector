from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.collection import Collection
from app.models.enums import CollectionStatus, SourceType
from app.schemas.collection import CollectionCreate, CollectionListOut, CollectionOut
from app.tasks import run_collection

router = APIRouter(prefix="/collections", tags=["collections"])


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
    query = select(Collection)
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
        select(Collection).where(Collection.id == collection_id)
    )
    collection = result.scalar_one_or_none()
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection
