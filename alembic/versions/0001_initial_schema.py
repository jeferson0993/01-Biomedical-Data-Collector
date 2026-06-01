"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "collections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.Enum("geo", "ncbi_gene", "pubmed", "uniprot", name="sourcetype"), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", name="collectionstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("raw_path", sa.String(), nullable=True),
        sa.Column("metadata_", JSONB, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "datasets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("collection_id", UUID(as_uuid=True), sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("format", sa.String(), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("checksum_sha256", sa.String(), nullable=True),
        sa.Column("minio_path", sa.String(), nullable=False),
    )

    op.create_index("ix_datasets_collection_id", "datasets", ["collection_id"])


def downgrade() -> None:
    op.drop_table("datasets")
    op.drop_table("collections")
    op.execute("DROP TYPE IF EXISTS collectionstatus")
    op.execute("DROP TYPE IF EXISTS sourcetype")
