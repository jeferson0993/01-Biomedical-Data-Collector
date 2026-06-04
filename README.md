# Project 1 — Biomedical Data Collector + Data Lake

Async API (FastAPI) for automated data collection from public bioinformatics repositories, with immutable storage in MinIO and metadata in PostgreSQL.

> ⚠️ **Independent project** — can be used standalone or as part of the Integrated Bioinformatics Platform. This documentation covers both scenarios.

---

## Dependencies

| Resource | Required | Provided by |
|----------|----------|-------------|
| PostgreSQL 16 | Yes | `postgres:16-alpine` (container) |
| MinIO | Yes | `minio/minio` (container) |
| Docker network `bioinfo-platform-net` | Yes | `docker network create` or root compose |
| Python 3.12+ | Dev only | — |
| `uv` | Dev only | `pip install uv` |

### Ports used

| Port | Service | Note |
|------|---------|------|
| 5432 | PostgreSQL | Internal to Docker network only |
| 9000 | MinIO (S3 API) | Internal only |
| 9001 | MinIO (Console) | Internal only |
| 8000 | API | Exposed to host |

---

## Configuration

### 1. Docker network

The `bioinfo-platform-net` network must exist **before** starting any container:

```bash
docker network create bioinfo-platform-net
```

### 2. Environment variables

```bash
cp .env.example .env
# Edit .env with your credentials
```

Variables available in `.env.example`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://platform:platform@postgres:5432/platform` | PostgreSQL connection string |
| `MINIO_ENDPOINT` | `minio:9000` | MinIO address (container name) |
| `MINIO_ACCESS_KEY` | `minioadmin` | MinIO access key |
| `MINIO_SECRET_KEY` | `minioadmin` | MinIO secret key |
| `MINIO_BUCKET` | `raw` | Bucket for raw data |
| `MINIO_SECURE` | `false` | Use TLS for MinIO |
| `NCBI_API_KEY` | — | NCBI API key (optional, raises limit from 3 req/s to 10 req/s) |
| `NCBI_EMAIL` | your email | Email required for E-utilities |
| `DOMAIN` | `localhost` | Domain used by CORS |
| `LOG_LEVEL` | `INFO` | Logging level |
| `POSTGRES_USER/PASSWORD/DB` | `platform` | Used by PostgreSQL container |
| `MINIO_ROOT_USER/PASSWORD` | `minioadmin` | Used by MinIO container |

> **Important:** In production, change all default passwords and set `MINIO_SECURE=true` with certificates.

---

## Scenario A — Full platform (recommended)

Uses the platform's root docker-compose, which provides PostgreSQL + MinIO + network.

```bash
# 1. At the platform root, start the shared infrastructure
cd ..
docker compose up -d postgres minio createbuckets

# 2. Return to this project and start the API
cd 01-coleta-dados
docker compose up -d --build

# 3. Run migrations
docker compose exec api alembic upgrade head

# 4. Test
curl http://localhost:8000/health
```

---

## Scenario B — Standalone project

To run only this project with its own PostgreSQL and MinIO instances, create a `docker-compose.standalone.yml`:

```yaml
name: bioinfo-01-coleta-dados

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: platform
      POSTGRES_PASSWORD: platform
      POSTGRES_DB: platform
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U platform"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - platform-net
    restart: unless-stopped

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - miniodata:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - platform-net
    restart: unless-stopped

  createbuckets:
    image: minio/mc
    depends_on:
      minio: { condition: service_healthy }
    entrypoint: >
      sh -c "
      mc alias set local http://minio:9000 minioadmin minioadmin &&
      mc mb local/raw --ignore-existing
      "
    networks:
      - platform-net

  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql+asyncpg://platform:platform@postgres:5432/platform
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: minioadmin
      MINIO_SECRET_KEY: minioadmin
      PYTHONPATH: /app
    volumes:
      - ./app:/app/app
    depends_on:
      postgres: { condition: service_healthy }
      minio: { condition: service_healthy }
      createbuckets: { condition: service_completed_successfully }
    networks:
      - platform-net
    restart: unless-stopped

volumes:
  pgdata:
  miniodata:

networks:
  platform-net:
    name: bioinfo-platform-net
```

```bash
# 1. Create network (first time only)
docker network create bioinfo-platform-net

# 2. Start everything
docker compose -f docker-compose.standalone.yml up -d --build

# 3. Run migrations
docker compose -f docker-compose.standalone.yml exec api alembic upgrade head

# 4. Test
curl http://localhost:8000/health
curl -X POST http://localhost:8000/collections \
  -H "Content-Type: application/json" \
  -d '{"source": "geo", "external_id": "GSE12345"}'
```

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────┐
│  FastAPI     │────▶│  Background  │────▶│ MinIO    │
│  (uvicorn)   │     │  Tasks       │     │ (raw/)   │
└──────┬───────┘     └──────┬───────┘     └──────────┘
       │                    │
       ▼                    ▼
┌──────────────┐    ┌──────────────┐
│  PostgreSQL  │    │  collectors  │
│  (metadata)  │    │  GEO, NCBI,  │
└──────────────┘    │  PubMed, Uni │
                    │  Prot        │
                    └──────────────┘
```

### Collection flow

```
POST /collections { source, external_id }
  → Creates Collection(status=pending) in PostgreSQL
  → Triggers background task:
    1. status = running
    2. Collector.fetch() → data from external source (with retry + backoff)
    3. Automatic rate limiting between requests
    4. Upload to MinIO: raw/{source}/{external_id}/
    5. Generates metadata.json with SHA-256 checksums alongside
    6. Applies MinIO tags (source, external_id) on each object
    7. Inserts Dataset records
    8. status = completed (or failed + error_message)
  → Returns 201 with collection_id
```

---

## Project structure

```
01-coleta-dados/
├── app/
│   ├── api/routes.py            # POST/GET /collections, upload, download
│   ├── collectors/              # GEO, NCBI Gene, PubMed, UniProt
│   │   ├── base.py              # AbstractCollector + rate limiting + retry
│   │   ├── geo/                 # SOFT format via NCBI GEO
│   │   ├── ncbi_gene/           # E-utilities esummary + efetch
│   │   ├── pubmed/              # E-utilities esummary + efetch
│   │   └── uniprot/             # REST API (XML + FASTA)
│   ├── models/                  # Collection, Dataset ORM + enums
│   ├── schemas/                 # Pydantic request/response
│   ├── storage/                 # MinIO client (cache, tags, list) + metadata
│   ├── utils/retry.py           # retry_async (exponential backoff)
│   ├── tasks.py                 # Background task runner
│   ├── config.py                # pydantic-settings
│   ├── database.py              # SQLAlchemy async engine
│   └── main.py                  # FastAPI app + /health (+ DB + MinIO checks)
├── alembic/                     # Migrations
│   └── versions/
│       ├── 0001_initial_schema.py
│       └── 0002_add_upload_source.py
├── tests/                       # 35 tests (pytest + respx)
│   ├── test_api/
│   ├── test_collectors/
│   ├── test_storage/
│   └── test_tasks/
├── docker-compose.yml           # API only (uses external network)
├── Dockerfile
├── .env.example
├── pyproject.toml
└── README.md
```

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Healthcheck (verifies PostgreSQL + MinIO) |
| `POST` | `/collections` | Trigger collection |
| `GET` | `/collections` | List collections (`?source=&status=&limit=&offset=`) |
| `GET` | `/collections/{id}` | Collection details + datasets |
| `POST` | `/collections/upload` | Manual file upload |
| `GET` | `/collections/{id}/download/{dataset_id}` | Dataset download |
| `POST` | `/collections/uniprot/batch` | Batch UniProt query |

### Examples

```bash
# Create collection
curl -X POST http://localhost:8000/collections \
  -H "Content-Type: application/json" \
  -d '{"source": "geo", "external_id": "GSE12345"}'

# List collections
curl "http://localhost:8000/collections?source=geo&limit=5"

# Manual upload
curl -X POST http://localhost:8000/collections/upload \
  -F "file=@my_data.fasta"

# Download
curl -o data.txt \
  "http://localhost:8000/collections/{id}/download/{dataset_id}"

# UniProt batch
curl -X POST http://localhost:8000/collections/uniprot/batch \
  -H "Content-Type: application/json" \
  -d '["P12345", "P67890"]'
```

---

## Collectors

| Collector | Source | Format | Authentication | Rate limit |
|-----------|--------|--------|----------------|------------|
| GEO | `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi` | SOFT text | Public | 10 req/s |
| NCBI Gene | E-utilities (`esummary` + `efetch`) | XML | API Key (optional) | 10 req/s |
| PubMed | E-utilities (`esummary` + `efetch`) | XML | API Key (optional) | 10 req/s |
| UniProt | `https://rest.uniprot.org/uniprotkb/` | XML + FASTA | Public | 10 req/s |

> Rate limit is configurable via `RATE_LIMIT_MAX_CALLS` and `RATE_LIMIT_PERIOD_SECONDS`.
> With `NCBI_API_KEY`, NCBI allows 10 req/s instead of 3 req/s without a key.

---

## Development (without Docker)

```bash
# Dependencies
pip install uv
uv sync --group dev

# Run PostgreSQL + MinIO locally (Docker)
docker run -d --name pg -e POSTGRES_PASSWORD=platform -p 5432:5432 postgres:16-alpine
docker run -d --name minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"

# Configure
cp .env.example .env
# Adjust DATABASE_URL to localhost if PG is on host

# Migrate
alembic upgrade head

# Run
uv run uvicorn app.main:app --reload

# Test
curl http://localhost:8000/health

# Quality
uv run ruff check app/ tests/
uv run mypy app/
uv run pytest tests/ -v
```

---

## Useful commands

```bash
# Access database
docker compose exec postgres psql -U platform -d platform

# View API logs
docker compose logs -f api

# List MinIO objects
docker compose exec minio mc ls local/raw/

# Shell into API container
docker compose exec api bash

# Rebuild + restart
docker compose up -d --build api
```

---

## Technologies

- **Python 3.12+**, FastAPI, SQLAlchemy 2.0 async, Pydantic v2
- **PostgreSQL 16** (asyncpg), **MinIO** (minio-py)
- **httpx** (async HTTP client), **respx** (test mocking)
- **ruff**, **mypy** (quality), **pytest** (testing)
- **Docker Compose**, **uv** (package manager)

---

## License

Internal project — Integrated Bioinformatics Platform.
