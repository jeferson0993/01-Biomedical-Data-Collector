from __future__ import annotations

import json
import logging
import subprocess
import uuid
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path("/app/scripts/r")
REPORTS_DIR = Path("/tmp/r_reports")


class RService:
    async def generate_report(self, collection_id: uuid.UUID, metadata: dict) -> str | None:
        outdir = REPORTS_DIR / str(collection_id)
        outdir.mkdir(parents=True, exist_ok=True)

        meta_path = outdir / "metadata.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f, default=str)

        try:
            result = subprocess.run(
                [
                    "Rscript", str(SCRIPTS_DIR / "collection_summary.R"),
                    "--collection_id", str(collection_id),
                    "--metadata", str(meta_path),
                    "--outdir", str(outdir),
                ],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                logger.error("R summary failed: %s", result.stderr)
                return None

            report_path = outdir / "report.html"
            if not report_path.exists():
                result = subprocess.run(
                    [
                        "R", "-e",
                        f"rmarkdown::render('{SCRIPTS_DIR / 'report_template.Rmd'}', "
                        f"params = list(collection_id = '{collection_id}'), "
                        f"output_dir = '{outdir}', output_file = 'report.html')",
                    ],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode != 0:
                    logger.error("RMarkdown render failed: %s", result.stderr)
                    return None

            if report_path.exists():
                html = report_path.read_text()
                return html

            logger.warning("Report not generated for %s", collection_id)
            return None

        except subprocess.TimeoutExpired:
            logger.warning("R script timed out for collection %s", collection_id)
            return None
        except Exception:
            logger.exception("R report generation failed for %s", collection_id)
            return None
