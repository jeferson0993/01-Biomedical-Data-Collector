FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    r-base \
    r-cran-rmarkdown \
    r-cran-knitr \
    r-cran-dplyr \
    r-cran-ggplot2 \
    r-cran-jsonlite \
    r-cran-optparse \
    r-cran-scales \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv --no-cache-dir

WORKDIR /app

COPY pyproject.toml .
RUN uv sync --no-dev --no-cache --no-install-project

COPY app/ /app/app/
COPY scripts/ /app/scripts/
COPY alembic.ini .
COPY alembic/ /app/alembic/
RUN uv sync --no-dev --no-cache

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--root-path", "/api/collector"]
