from __future__ import annotations

import enum


class SourceType(enum.StrEnum):
    geo = "geo"
    ncbi_gene = "ncbi_gene"
    pubmed = "pubmed"
    uniprot = "uniprot"
    upload = "upload"


class CollectionStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
