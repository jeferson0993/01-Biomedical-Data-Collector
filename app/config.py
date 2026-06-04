from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://platform:platform@localhost:5432/platform"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "raw"
    minio_secure: bool = False

    ncbi_api_key: str = ""
    ncbi_email: str = "user@example.com"

    uniprot_base_url: str = "https://rest.uniprot.org"

    domain: str = "localhost"

    log_level: str = "INFO"

    rate_limit_max_calls: int = 10
    rate_limit_period_seconds: float = 1.0


settings = Settings()
