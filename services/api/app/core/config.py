"""Application configuration management."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=(".env",), env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "staging", "production"] = Field(default="local", alias="APP_ENV")
    api_key: str | None = Field(default=None, alias="API_KEY")
    database_url: str = Field(..., alias="DATABASE_URL")
    aws_region: str | None = Field(default=None, alias="AWS_REGION")
    s3_bucket_name: str | None = Field(default=None, alias="S3_BUCKET_NAME")
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")

    @field_validator("cors_origins")
    @classmethod
    def normalize_origins(cls, value: str) -> str:
        return value or ""

    @model_validator(mode="after")
    def validate_required_non_local(self) -> "Settings":
        if self.app_env in {"staging", "production"}:
            missing: list[str] = []
            if not self.api_key:
                missing.append("API_KEY")
            if not self.aws_region:
                missing.append("AWS_REGION")
            if not self.s3_bucket_name:
                missing.append("S3_BUCKET_NAME")
            if missing:
                joined = ", ".join(missing)
                raise ValueError(f"Missing required environment variables: {joined}")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return origins or ["http://localhost:5173"]

    @property
    def is_secure_env(self) -> bool:
        return self.app_env in {"staging", "production"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
