# Projeto 1 — Biomedical Data Collector + Data Lake

API assíncrona (FastAPI) para coleta automatizada de dados de repositórios públicos de bioinformática, com armazenamento imutável em MinIO e metadados em PostgreSQL.

> ⚠️ **Projeto independente** — pode ser usado sozinho ou como parte da Plataforma Integrada de Bioinformática. Esta documentação cobre ambos os cenários.

---

## Dependências

| Recurso | Obrigatório | Fornecido por |
|---------|-------------|---------------|
| PostgreSQL 16 | Sim | `postgres:16-alpine` (container) |
| MinIO | Sim | `minio/minio` (container) |
| Rede Docker `bioinfo-platform-net` | Sim | `docker network create` ou compose raiz |
| Python 3.12+ | Apenas dev | — |
| `uv` | Apenas dev | `pip install uv` |

### Portas utilizadas

| Porta | Serviço | Observação |
|-------|---------|------------|
| 5432 | PostgreSQL | Apenas interno da rede Docker |
| 9000 | MinIO (API S3) | Apenas interno |
| 9001 | MinIO (Console) | Apenas interno |
| 8000 | API | Exposta para o host |

---

## Configuração

### 1. Rede Docker

A rede `bioinfo-platform-net` deve existir **antes** de subir qualquer container:

```bash
docker network create bioinfo-platform-net
```

### 2. Variáveis de ambiente

```bash
cp .env.example .env
# Edite .env com suas credenciais
```

Variáveis disponíveis no `.env.example`:

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `DATABASE_URL` | `postgresql+asyncpg://platform:platform@postgres:5432/platform` | Conexão com PostgreSQL |
| `MINIO_ENDPOINT` | `minio:9000` | Endereço do MinIO (nome do container) |
| `MINIO_ACCESS_KEY` | `minioadmin` | Access key MinIO |
| `MINIO_SECRET_KEY` | `minioadmin` | Secret key MinIO |
| `MINIO_BUCKET` | `raw` | Bucket para dados brutos |
| `MINIO_SECURE` | `false` | Usar TLS para MinIO |
| `NCBI_API_KEY` | — | Chave de API NCBI (opcional, aumenta limite de 3 req/s para 10 req/s) |
| `NCBI_EMAIL` | seu email | Email obrigatório para E-utilities |
| `DOMAIN` | `localhost` | Domínio usado pelo CORS |
| `LOG_LEVEL` | `INFO` | Nível de logging |
| `POSTGRES_USER/PASSWORD/DB` | `platform` | Usado pelo container PostgreSQL |
| `MINIO_ROOT_USER/PASSWORD` | `minioadmin` | Usado pelo container MinIO |

> **Importante:** Em produção, altere todas as senhas padrão e use `MINIO_SECURE=true` com certificados.

---

## Cenário A — Plataforma completa (recomendado)

Usa o docker-compose raiz da plataforma, que fornece PostgreSQL + MinIO + rede.

```bash
# 1. Na raiz da plataforma, sobe a infraestrutura compartilhada
cd ..
docker compose up -d postgres minio createbuckets

# 2. Volta para este projeto e sobe a API
cd 01-coleta-dados
docker compose up -d --build

# 3. Executa migrações
docker compose exec api alembic upgrade head

# 4. Testa
curl http://localhost:8000/health
```

---

## Cenário B — Projeto standalone

Para executar apenas este projeto com suas próprias instâncias de PostgreSQL e MinIO, crie um `docker-compose.standalone.yml`:

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
# 1. Criar rede (apenas na primeira vez)
docker network create bioinfo-platform-net

# 2. Subir tudo
docker compose -f docker-compose.standalone.yml up -d --build

# 3. Executar migrações
docker compose -f docker-compose.standalone.yml exec api alembic upgrade head

# 4. Testar
curl http://localhost:8000/health
curl -X POST http://localhost:8000/collections \
  -H "Content-Type: application/json" \
  -d '{"source": "geo", "external_id": "GSE12345"}'
```

---

## Arquitetura

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

### Fluxo de coleta

```
POST /collections { source, external_id }
  → Cria Collection(status=pending) no PostgreSQL
  → Dispara background task:
    1. status = running
    2. Coletor.fetch() → dados da fonte externa (com retry + backoff)
    3. Rate limiting automático entre requisições
    4. Upload para MinIO: raw/{source}/{external_id}/
    5. Gera metadata.json com checksums SHA-256 lado a lado
    6. Aplica tags MinIO (source, external_id) em cada objeto
    7. Insere Dataset records
    8. status = completed (ou failed + error_message)
  → Retorna 201 com collection_id
```

---

## Estrutura do projeto

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
├── tests/                       # 35 testes (pytest + respx)
│   ├── test_api/
│   ├── test_collectors/
│   ├── test_storage/
│   └── test_tasks/
├── docker-compose.yml           # Apenas API (usa rede externa)
├── Dockerfile
├── .env.example
├── pyproject.toml
└── README.md
```

---

## Endpoints

| Método | Caminho | Descrição |
|--------|---------|----------|
| `GET` | `/health` | Healthcheck (verifica PostgreSQL + MinIO) |
| `POST` | `/collections` | Disparar coleta |
| `GET` | `/collections` | Listar coleções (`?source=&status=&limit=&offset=`) |
| `GET` | `/collections/{id}` | Detalhes da coleta + datasets |
| `POST` | `/collections/upload` | Upload manual de arquivo |
| `GET` | `/collections/{id}/download/{dataset_id}` | Download de dataset |
| `POST` | `/collections/uniprot/batch` | Consulta UniProt em lote |

### Exemplos

```bash
# Criar coleta
curl -X POST http://localhost:8000/collections \
  -H "Content-Type: application/json" \
  -d '{"source": "geo", "external_id": "GSE12345"}'

# Listar coleções
curl "http://localhost:8000/collections?source=geo&limit=5"

# Upload manual
curl -X POST http://localhost:8000/collections/upload \
  -F "file=@meus_dados.fasta"

# Download
curl -o dados.txt \
  "http://localhost:8000/collections/{id}/download/{dataset_id}"

# UniProt batch
curl -X POST http://localhost:8000/collections/uniprot/batch \
  -H "Content-Type: application/json" \
  -d '["P12345", "P67890"]'
```

---

## Coletores

| Coletor | Fonte | Formato | Autenticação | Rate limit |
|---------|-------|---------|-------------|------------|
| GEO | `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi` | SOFT text | Pública | 10 req/s |
| NCBI Gene | E-utilities (`esummary` + `efetch`) | XML | API Key (opcional) | 10 req/s |
| PubMed | E-utilities (`esummary` + `efetch`) | XML | API Key (opcional) | 10 req/s |
| UniProt | `https://rest.uniprot.org/uniprotkb/` | XML + FASTA | Pública | 10 req/s |

> O rate limit é configurável via `RATE_LIMIT_MAX_CALLS` e `RATE_LIMIT_PERIOD_SECONDS`.
> Com `NCBI_API_KEY`, o NCBI permite 10 req/s em vez de 3 req/s sem chave.

---

## Desenvolvimento (sem Docker)

```bash
# Dependências
pip install uv
uv sync --group dev

# Executar PostgreSQL + MinIO localmente (Docker)
docker run -d --name pg -e POSTGRES_PASSWORD=platform -p 5432:5432 postgres:16-alpine
docker run -d --name minio -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"

# Configurar
cp .env.example .env
# Ajuste DATABASE_URL para localhost se o PG estiver no host

# Migrar
alembic upgrade head

# Rodar
uv run uvicorn app.main:app --reload

# Testar
curl http://localhost:8000/health

# Qualidade
uv run ruff check app/ tests/
uv run mypy app/
uv run pytest tests/ -v
```

---

## Comandos úteis

```bash
# Acessar banco
docker compose exec postgres psql -U platform -d platform

# Ver logs da API
docker compose logs -f api

# Listar objetos no MinIO
docker compose exec minio mc ls local/raw/

# Shell no container da API
docker compose exec api bash

# rebuild + restart
docker compose up -d --build api
```

---

## Tecnologias

- **Python 3.12+**, FastAPI, SQLAlchemy 2.0 async, Pydantic v2
- **PostgreSQL 16** (asyncpg), **MinIO** (minio-py)
- **httpx** (client HTTP async), **respx** (mock em testes)
- **ruff**, **mypy** (qualidade), **pytest** (testes)
- **Docker Compose**, **uv** (package manager)

---

## Licença

Projeto interno — Plataforma Integrada de Bioinformática.
