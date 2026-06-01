# Projeto 1 — Biomedical Data Collector + Data Lake

API FastASync para coleta automatizada de dados de repositórios públicos de bioinformática, com armazenamento imutável em MinIO e metadados em PostgreSQL.

## Arquitetura

```
┌─────────────┐     ┌──────────────┐     ┌──────────┐
│  FastAPI    │────▶│  Background  │────▶│ MinIO    │
│  (uvicorn)  │     │  Tasks       │     │ (raw/)   │
└──────┬──────┘     └──────┬───────┘     └──────────┘
       │                   │
       ▼                   ▼
┌──────────────┐    ┌──────────────┐
│  PostgreSQL  │    │  collectors  │
│  (metadata)  │    │  GEO, NCBI,  │
└──────────────┘    │  PubMed, Uni │
                    │  Prot        │
                    └──────────────┘
```

### Serviços (Docker Compose)

| Serviço | Imagem | Função |
|---------|--------|--------|
| `api` | python:3.12-slim (build local) | FastAPI na porta 8000 |
| `postgres` | postgres:16-alpine | Metadados das coleções |
| `minio` | minio/minio | Armazenamento de dados brutos (portas 9000/9001) |
| `createbuckets` | minio/mc (one-shot) | Cria bucket `raw` na inicialização |

## Stack

- **Runtime**: Python 3.12+, FastAPI, SQLAlchemy 2.0 async, Pydantic v2
- **Storage**: PostgreSQL 16 (asyncpg), MinIO (minio-py)
- **Coletores**: httpx + respx (testes)
- **Infra**: Docker Compose, uv
- **Qualidade**: ruff, mypy, pytest

## Estrutura

```
01-coleta-dados/
├── app/
│   ├── api/routes.py          # POST/GET /collections
│   ├── collectors/            # GEO, NCBI Gene, PubMed, UniProt
│   │   ├── base.py            # AbstractCollector
│   │   ├── geo/               # SOFT format via NCBI GEO
│   │   ├── ncbi_gene/         # E-utilities esummary + efetch
│   │   ├── pubmed/            # E-utilities esummary + efetch
│   │   └── uniprot/           # REST API (XML + FASTA)
│   ├── models/                # Collection, Dataset ORM + enums
│   ├── schemas/               # Pydantic request/response
│   ├── storage/               # MinIO client + metadata helper
│   ├── utils/retry.py         # retry_async (exponential backoff)
│   ├── tasks.py               # Background task runner
│   ├── config.py              # pydantic-settings
│   ├── database.py            # SQLAlchemy async engine
│   └── main.py                # FastAPI app + /health
├── alembic/                   # Migrations
├── tests/                     # 21 testes
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── pyproject.toml
```

## Quick Start

```bash
# 1. Copiar env
cp .env.example .env

# 2. Subir serviços
docker compose up -d

# 3. Executar migrações
docker compose exec api alembic upgrade head

# 4. Testar
curl http://localhost:8000/health
curl -X POST http://localhost:8000/collections \
  -H "Content-Type: application/json" \
  -d '{"source": "geo", "external_id": "GSE12345"}'
```

## Desenvolvimento (sem Docker)

```bash
uv sync
uv run ruff check app/ tests/
uv run mypy app/
uv run pytest tests/ -v
```

## Endpoints

| Método | Caminho | Descrição |
|--------|---------|----------|
| `GET` | `/health` | Healthcheck |
| `POST` | `/collections` | Disparar coleta |
| `GET` | `/collections` | Listar coleções (filtros: `?source=&status=&limit=&offset=`) |
| `GET` | `/collections/{id}` | Detalhes da coleta + datasets |

## Coletores

| Coletor | Fonte | Formato | Autenticação |
|---------|-------|---------|-------------|
| GEO | `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi` | SOFT text | Pública |
| NCBI Gene | E-utilities (`esummary` + `efetch`) | XML | API Key (opcional) |
| PubMed | E-utilities (`esummary` + `efetch`) | XML | API Key (opcional) |
| UniProt | `https://rest.uniprot.org/uniprotkb/` | XML + FASTA | Pública |

## Fluxo de Coleta

```
POST /collections { source, external_id }
  → Cria Collection(status=pending) no PostgreSQL
  → Dispara background task:
    1. status = running
    2. Coletor.fetch() → dados da fonte externa (com retry + backoff)
    3. Upload para MinIO: raw/{source}/{external_id}/
    4. Gera metadata.json lado a lado
    5. Insere Dataset records
    6. status = completed (ou failed + error_message)
  → Retorna 201 com collection_id
```

## Licença

Projeto interno — Plataforma Integrada de Bioinformática.
