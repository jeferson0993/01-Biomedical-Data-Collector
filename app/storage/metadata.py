from __future__ import annotations

from datetime import UTC, datetime


def build_metadata(
    source: str,
    source_version: str = "",
    parameters: dict[str, object] | None = None,
    checksums: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "source": source,
        "date": datetime.now(UTC).isoformat(),
        "created_at": datetime.now(UTC).isoformat(),
        "source_version": source_version or "unknown",
        "parameters": parameters or {},
        "checksums": checksums or [],
    }
