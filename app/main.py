from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as collections_router
from app.config import settings
from app.database import async_session
from app.storage.minio_client import MinioClient

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    logger.info("Starting Biomedical Data Collector")

    _app.state.http_client = httpx.AsyncClient()
    logger.info("Shared HTTP client created")

    mc = MinioClient()
    await mc.ensure_bucket()
    logger.info("MinIO bucket '%s' ensured", mc.bucket)

    yield

    logger.info("Closing shared HTTP client")
    await _app.state.http_client.aclose()

    # Close module-level collector clients
    import app.collectors.geo.collector as geo_c
    import app.collectors.ncbi_gene.collector as ng_c
    import app.collectors.pubmed.collector as pm_c
    import app.collectors.uniprot.collector as uni_c

    for mod in (geo_c, ng_c, pm_c, uni_c):
        if hasattr(mod, "_client"):
            await mod._client.aclose()
    logger.info("Module-level HTTP clients closed")


origins = [
    f"https://{settings.domain}",
    "http://localhost:5173",
    "http://localhost:8000",
]
app = FastAPI(
    title="Biomedical Data Collector",
    description="API para coleta de dados de repositórios públicos de bioinformática",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(collections_router)


@app.get("/health")
async def health() -> dict[str, object]:
    sub_checks: dict[str, str] = {}
    status = "ok"

    try:
        async with async_session() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
        sub_checks["database"] = "ok"
    except Exception as exc:
        sub_checks["database"] = f"error: {exc}"
        status = "degraded"

    try:
        mc = MinioClient()
        await mc.object_exists("health-check-probe")
        sub_checks["minio"] = "ok"
    except Exception as exc:
        sub_checks["minio"] = f"error: {exc}"
        status = "degraded"

    return {
        "status": status,
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": sub_checks,
    }
