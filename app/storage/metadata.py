from __future__ import annotations

from datetime import UTC, datetime


def build_metadata(
    source: str,
    source_version: str = "",
    parameters: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "source": source,
        "date": datetime.now(UTC).isoformat(),
        "version": source_version or "unknown",
        "parameters": parameters or {},
    }
