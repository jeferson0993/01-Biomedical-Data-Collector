FROM python:3.12-slim

RUN pip install uv --no-cache-dir

WORKDIR /app

COPY pyproject.toml .
RUN uv sync --no-dev --no-cache

COPY app/ /app/app/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
