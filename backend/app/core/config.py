"""Application configuration (pydantic-settings)."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "EduPay"
    env: str = "development"
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+psycopg2://edupay:edupay@localhost:5432/edupay"
    )

    jwt_secret: str = "change-me-in-prod-please-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Stored as a CSV string to avoid pydantic-settings JSON-parsing the env
    # value (which fails on plain `http://localhost:3000`). Splits via the
    # `cors_origins_list` property below.
    cors_origins: str = "http://localhost:3000"

    mock_gateway_url: str = "http://localhost:8000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
