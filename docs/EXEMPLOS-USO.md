# Documentação Exemplificada — Projeto 1

## Coleta de Dados Biológicos via API

Este documento apresenta exemplos práticos de uso da API de coleta de dados,
desde o disparo de uma coleta até a verificação dos resultados no MinIO.

---

## 1. Healthcheck

Verificar se o serviço está no ar:

```bash
curl http://localhost:8000/health
```

Resposta esperada:

```json
{ "status": "ok" }
```

---

## 2. Disparar uma Coleta

### 2.1 Coletar um dataset GEO

O repositório GEO (Gene Expression Omnibus) armazena dados de expressão gênica.
O identificador de um estudo GEO começa com `GSE` seguido de dígitos.

**Exemplo:** Baixar o estudo GSE12345 (dados hipotéticos de expressão em câncer de mama):

```bash
curl -X POST http://localhost:8000/collections \
  -H "Content-Type: application/json" \
  -d '{
    "source": "geo",
    "external_id": "GSE12345"
  }'
```

Resposta esperada (201 Created):

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "source": "geo",
  "external_id": "GSE12345",
  "status": "pending",
  "raw_path": null,
  "metadata_": null,
  "error_message": null,
  "created_at": "2026-06-01T12:00:00",
  "updated_at": "2026-06-01T12:00:00",
  "datasets": []
}
```

O campo `status` muda para `running` enquanto a coleta ocorre em segundo plano
e para `completed` quando termina.

### 2.2 Coletar um gene do NCBI

O NCBI Gene usa identificadores numéricos.

**Exemplo 1:** gene TP53 (id 7157):

```bash
curl -X POST http://localhost:8000/collections \
  -H "Content-Type: application/json" \
  -d '{
    "source": "ncbi_gene",
    "external_id": "7157"
  }'
```

**Exemplo 2:** gene IL6 (id 3569):

```bash
curl -X POST http://localhost:8000/collections \
  -H "Content-Type: application/json" \
  -d '{
    "source": "ncbi_gene",
    "external_id": "3569"
  }'
```

### 2.3 Coletar um artigo do PubMed

**Exemplo:** PMID 12345678:

```bash
curl -X POST http://localhost:8000/collections \
  -H "Content-Type: application/json" \
  -d '{
    "source": "pubmed",
    "external_id": "12345678"
  }'
```

### 2.4 Coletar uma proteína do UniProt

**Exemplo:** Proteína TP53 humana (accession P04637):

```bash
curl -X POST http://localhost:8000/collections \
  -H "Content-Type: application/json" \
  -d '{
    "source": "uniprot",
    "external_id": "P04637"
  }'
```

### 2.5 Coletar com parâmetros adicionais

É possível enviar parâmetros extras que serão armazenados como metadados:

```bash
curl -X POST http://localhost:8000/collections \
  -H "Content-Type: application/json" \
  -d '{
    "source": "geo",
    "external_id": "GSE12345",
    "params": {
      "formato": "soft",
      "prioridade": "alta",
      "responsavel": "pesquisador_a"
    }
  }'
```

---

## 3. Consultar Coleções

### 3.1 Listar todas as coleções

```bash
curl http://localhost:8000/collections
```

Resposta:

```json
{
  "items": [
    {
      "id": "a1b2c3d4-...",
      "source": "geo",
      "external_id": "GSE12345",
      "status": "completed",
      "datasets": ["..."],
      ...
    }
  ],
  "total": 1
}
```

### 3.2 Filtrar por fonte

```bash
curl "http://localhost:8000/collections?source=uniprot"
```

### 3.3 Filtrar por status

```bash
curl "http://localhost:8000/collections?status=failed"
```

### 3.4 Paginação

```bash
curl "http://localhost:8000/collections?limit=10&offset=0"
```

### 3.5 Detalhes de uma coleta específica

```bash
curl http://localhost:8000/collections/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

Resposta com datasets:

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "source": "ncbi_gene",
  "external_id": "7157",
  "status": "completed",
  "raw_path": "ncbi_gene/7157",
  "metadata_": {
    "source": "ncbi_gene",
    "date": "2026-06-01T12:00:00",
    "version": "unknown",
    "parameters": {}
  },
  "error_message": null,
  "created_at": "2026-06-01T12:00:00",
  "updated_at": "2026-06-01T12:00:10",
  "datasets": [
    {
      "id": "f6e5d4c3-...",
      "filename": "7157_summary.xml",
      "format": "xml",
      "file_size": null,
      "checksum_sha256": null,
      "minio_path": "raw/ncbi_gene/7157/7157_summary.xml"
    },
    {
      "id": "b2a1c3d4-...",
      "filename": "7157_full.xml",
      "format": "xml",
      "file_size": null,
      "checksum_sha256": null,
      "minio_path": "raw/ncbi_gene/7157/7157_full.xml"
    }
  ]
}
```

---

## 4. Upload de Arquivos

Faça upload de um arquivo do seu computador diretamente para o MinIO via API. Útil para enviar arquivos FASTA, FASTQ, TXT, ou qualquer dado complementar.

### 4.1 Upload de arquivo

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@/caminho/para/meu_gene.fasta"
```

Resposta esperada (201 Created):

```json
{
  "id": "uuid-da-colecao",
  "source": "upload",
  "external_id": "meu_gene.fasta",
  "status": "completed",
  "raw_path": "upload/uuid-da-colecao",
  "datasets": [
    {
      "id": "uuid-do-dataset",
      "filename": "meu_gene.fasta",
      "format": "fasta",
      "file_size": 1234,
      "checksum_sha256": null,
      "minio_path": "raw/upload/uuid-da-colecao/meu_gene.fasta"
    }
  ],
  ...
}
```

O arquivo é armazenado no bucket `raw/upload/{collection_id}/{filename}`.

### 4.2 Download de arquivo

Para baixar um arquivo de uma coleta (upload ou coleta automática):

```bash
# Obter o ID da coleta e o ID do dataset
curl -s http://localhost:8000/collections/{collection_id} | jq '.datasets[] | {id, filename}'

# Baixar o arquivo
curl -O http://localhost:8000/collections/{collection_id}/download/{dataset_id}
```

Exemplo completo:

```bash
# 1. Fazer upload
UPLOAD=$(curl -s -X POST http://localhost:8000/upload -F "file=@dados.fasta")
COLLECTION_ID=$(echo "$UPLOAD" | jq -r '.id')
DATASET_ID=$(echo "$UPLOAD" | jq -r '.datasets[0].id')

# 2. Baixar o arquivo de volta
curl -o baixado.fasta "http://localhost:8000/collections/$COLLECTION_ID/download/$DATASET_ID"
```

---

## 5. Estrutura no MinIO

Quando uma coleta é concluída, os dados são armazenados no MinIO dentro do
bucket `raw` na seguinte estrutura:

```
raw/
├── geo/
│   └── GSE12345/
│       ├── GSE12345.soft
│       └── metadata.json
├── ncbi_gene/
│   └── 7157/
│       ├── 7157_summary.xml
│       ├── 7157_full.xml
│       └── metadata.json
├── pubmed/
│   └── 12345678/
│       ├── 12345678_summary.xml
│       ├── 12345678_full.xml
│       └── metadata.json
├── uniprot/
│   └── P04637/
│       ├── P04637.xml
│       ├── P04637.fasta
│       └── metadata.json
└── upload/
    └── {collection_id}/
        ├── meu_arquivo.fasta
        └── metadata.json
```

### Arquivo metadata.json

Cada coleta gera automaticamente um arquivo `metadata.json` no formato
padronizado:

```json
{
  "source": "geo",
  "date": "2026-06-01T12:00:00+00:00",
  "version": "unknown",
  "parameters": {}
}
```

---

## 6. Exemplos de Código

### 6.1 Python com httpx

```python
import httpx

BASE_URL = "http://localhost:8000"

# Disparar coleta
response = httpx.post(
    f"{BASE_URL}/collections",
    json={"source": "uniprot", "external_id": "P04637"},
)
collection = response.json()
print(f"Collection ID: {collection['id']}")

# Aguardar conclusão (polling simples)
import time
while True:
    resp = httpx.get(f"{BASE_URL}/collections/{collection['id']}")
    data = resp.json()
    if data["status"] in ("completed", "failed"):
        print(f"Status: {data['status']}")
        break
    time.sleep(2)
```

### 6.2 Python com o cliente assíncrono

```python
import asyncio
import httpx


async def collect_and_wait():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        resp = await client.post(
            "/collections",
            json={"source": "pubmed", "external_id": "12345678"},
        )
        coll = resp.json()
        print(f"Disparada coleta {coll['id']}")

        while True:
            resp = await client.get(f"/collections/{coll['id']}")
            data = resp.json()
            print(f"Status: {data['status']}")
            if data["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(2)


asyncio.run(collect_and_wait())
```

### 6.3 Bash com jq

```bash
#!/usr/bin/env bash
set -euo pipefail

API="http://localhost:8000"

# Disparar coleta GEO
echo "=== Disparando coleta GEO ==="
RESP=$(curl -s -X POST "$API/collections" \
  -H "Content-Type: application/json" \
  -d '{"source": "geo", "external_id": "GSE12345"}')
ID=$(echo "$RESP" | jq -r '.id')
echo "Collection ID: $ID"

# Polling até completar
while true; do
  STATUS=$(curl -s "$API/collections/$ID" | jq -r '.status')
  echo "Status: $STATUS"
  [ "$STATUS" = "completed" ] && break
  [ "$STATUS" = "failed" ] && echo "Falhou!" && exit 1
  sleep 2
done

# Listar datasets
curl -s "$API/collections/$ID" | jq '.datasets[] | {filename, minio_path}'
```

---

## 7. Cenários de Uso

### 7.1 Pipeline: Coletar gene → analisar variantes

```bash
# 1. Coletar gene TP53
curl -s -X POST http://localhost:8000/collections \
  -H "Content-Type: application/json" \
  -d '{"source": "ncbi_gene", "external_id": "7157"}'

# 2. Coletar artigos PubMed sobre TP53
curl -s -X POST http://localhost:8000/collections \
  -H "Content-Type: application/json" \
  -d '{"source": "pubmed", "external_id": "12345678"}'

# 3. Coletar proteína do UniProt
curl -s -X POST http://localhost:8000/collections \
  -H "Content-Type: application/json" \
  -d '{"source": "uniprot", "external_id": "P04637"}'

# 4. Verificar tudo
curl -s http://localhost:8000/collections | jq '.items[] | {source, external_id, status}'
```

### 7.2 Ambiente de desenvolvimento sem Docker

```bash
# Instalar dependências
uv sync

# Iniciar apenas a API (requer PostgreSQL e MinIO externos)
uv run uvicorn app.main:app --reload --port 8000

# Executar testes
uv run pytest tests/ -v

# Verificar tipagem
uv run mypy app/

# Verificar lint
uv run ruff check app/ tests/
```

### 7.3 Ambiente com Docker Compose

```bash
# Subir infra compartilhada (postgres + minio + gateway)
docker compose up -d

# Subir API do Projeto 1
docker compose -f 01-coleta-dados/docker-compose.yml up -d

# Ver logs da API
docker compose -f 01-coleta-dados/docker-compose.yml logs -f api

# Executar migrations
docker compose -f 01-coleta-dados/docker-compose.yml exec api uv run alembic upgrade head

# Acessar console MinIO
# http://localhost:9001 (minioadmin / minioadmin)

# Parar tudo
docker compose down
docker compose -f 01-coleta-dados/docker-compose.yml down

# Parar e remover volumes (dados são perdidos)
docker compose down -v
```

---

## 8. Tratamento de Erros

### 8.1 Coleta com external_id inválido

```bash
curl -s -X POST http://localhost:8000/collections \
  -H "Content-Type: application/json" \
  -d '{"source": "geo", "external_id": "ID_INEXISTENTE"}'
```

A coleta será criada com `status=pending`, mas a tarefa em segundo plano falhará e o status mudará para `failed` com uma mensagem de erro:

```json
{
  "id": "...",
  "status": "failed",
  "error_message": "HTTP 404: Not Found for url..."
}
```

### 8.2 Fonte inválida

```bash
curl -s -X POST http://localhost:8000/collections \
  -H "Content-Type: application/json" \
  -d '{"source": "fontedesconhecida", "external_id": "X"}'
```

Resposta (422 Unprocessable Entity):

```json
{
  "detail": [
    {
      "type": "enum",
      "loc": ["body", "source"],
      "msg": "Input should be 'geo', 'ncbi_gene', 'pubmed', 'uniprot' or 'upload'"
    }
  ]
}
```

### 8.3 Collection não encontrada

```bash
curl -s http://localhost:8000/collections/00000000-0000-0000-0000-000000000000
```

Resposta (404):

```json
{ "detail": "Collection not found" }
```

---

## 9. Métricas e Monitoramento

O serviço expõe logs estruturados em JSON no stdout. Para visualizar:

```bash
docker compose logs -f api | jq 'select(.level == "ERROR")'
```

Para monitoramento com Prometheus/Grafana (planejado para fases futuras), os endpoints `/health` podem ser usados como probe de存活idade (liveness).

---

## 10. Boas Práticas

1. **Rate limiting**: A API respeita os limites definidos em `NCBI_API_KEY`
   e `RATE_LIMIT_MAX_CALLS` no `.env`. Com `api_key`, o NCBI permite 10 req/s;
   sem `api_key`, 3 req/s.
2. **Dados imutáveis**: Uma vez no MinIO, os dados não são alterados.
   Cada coleta gera novos arquivos. Não reutilizar `external_id` para
   obter dados atualizados — crie uma nova coleta.
3. **Metadados**: Todo conjunto de dados possui `metadata.json` lado a lado
   no MinIO, conforme a convenção do repositório.
4. **Identificadores**: Use sempre UUIDs para referências internas.
   Os IDs externos (GSE12345, 7157, P04637) são armazenados em `external_id`.
