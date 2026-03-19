"""Application configuration management."""

from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BASE_DIR.parent.parent

ENV_FILES = tuple(
    str(path)
    for path in (
        BASE_DIR / ".env",
        ROOT_DIR / ".env",
    )
)

AppEnv = Literal["local", "staging", "production"]


class Settings(BaseSettings):
    """Central application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=ENV_FILES, env_file_encoding="utf-8", extra="ignore")

    app_env: AppEnv = Field(..., alias="APP_ENV")
    database_url: str = Field(..., alias="DATABASE_URL")
    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    supabase_public_key: str | None = Field(
        default=None,
        alias="SUPABASE_PUBLISHABLE_KEY",
        validation_alias=AliasChoices("SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY"),
    )
    supabase_service_role_key: str | None = Field(default=None, alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_storage_bucket: str | None = Field(default=None, alias="SUPABASE_STORAGE_BUCKET")
    supabase_jwt_audience: str = Field(default="authenticated", alias="SUPABASE_JWT_AUDIENCE")
    local_auth_bypass: bool | None = Field(default=None, alias="LOCAL_AUTH_BYPASS")
    local_auth_user_id: uuid.UUID = Field(
        default=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        alias="LOCAL_AUTH_USER_ID",
    )
    local_auth_email: str = Field(
        default="local-user@styleus.invalid",
        alias="LOCAL_AUTH_EMAIL",
    )
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")

    media_root: str = Field(default="./media", alias="MEDIA_ROOT")
    media_max_upload_size: int = Field(default=15 * 1024 * 1024, alias="MEDIA_MAX_UPLOAD_SIZE")
    supabase_signed_url_ttl_seconds: int = Field(
        default=3600,
        alias="SUPABASE_SIGNED_URL_TTL_SECONDS",
    )
    run_migrations_on_start: bool | None = Field(
        default=None,
        alias="RUN_MIGRATIONS_ON_START",
    )
    run_seed_on_start: bool | None = Field(
        default=None,
        alias="RUN_SEED_ON_START",
        validation_alias=AliasChoices("RUN_SEED_ON_START", "SEED_ON_START"),
    )
    seed_limit: int = Field(default=25, alias="SEED_LIMIT")
    seed_key: str = Field(default="local-seed-v1", alias="SEED_KEY")
    ai_enable_classifier: bool = Field(default=True, alias="AI_ENABLE_CLASSIFIER")
    ai_device: str = Field(default="cpu", alias="AI_DEVICE")
    ai_model_name: str = Field(default="hf-hub:Marqo/marqo-fashionCLIP", alias="AI_MODEL_NAME")
    ai_model_pretrained: str | None = Field(default=None, alias="AI_MODEL_PRETRAINED")
    ai_model_cache_dir: str = Field(default="./media/.model_cache", alias="AI_MODEL_CACHE_DIR")
    ai_onnx: bool = Field(default=False, alias="AI_ONNX")
    ai_confidence_threshold: float = Field(default=0.6, alias="AI_CONFIDENCE_THRESHOLD")
    ai_subcategory_confidence_threshold: float = Field(
        default=0.5,
        alias="AI_SUBCATEGORY_CONFIDENCE_THRESHOLD",
    )
    ai_tag_confidence_threshold: float = Field(default=0.28, alias="AI_TAG_CONFIDENCE_THRESHOLD")
    ai_color_use_mask: bool = Field(default=True, alias="AI_COLOR_USE_MASK")
    ai_color_mask_method: Literal["grabcut", "heuristic"] = Field(
        default="grabcut", alias="AI_COLOR_MASK_METHOD"
    )
    ai_color_min_foreground_pixels: int = Field(
        default=3000, alias="AI_COLOR_MIN_FOREGROUND_PIXELS"
    )
    ai_color_topk: int = Field(default=2, alias="AI_COLOR_TOPK")
    ai_onnx_model_path: str | None = Field(default=None, alias="AI_ONNX_MODEL_PATH")
    ai_job_max_attempts: int = Field(default=3, alias="AI_JOB_MAX_ATTEMPTS")
    ai_job_poll_interval_seconds: float = Field(default=0.5, alias="AI_JOB_POLL_INTERVAL_SECONDS")
    ai_job_stale_after_seconds: int = Field(default=300, alias="AI_JOB_STALE_AFTER_SECONDS")
    supabase_http_timeout_seconds: float = Field(
        default=15.0,
        alias="SUPABASE_HTTP_TIMEOUT_SECONDS",
    )

    @field_validator("cors_origins")
    @classmethod
    def normalize_origins(cls, value: str) -> str:
        return value or ""

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        normalized = value.strip()
        if normalized.startswith("postgresql+psycopg://"):
            return normalized
        if normalized.startswith("postgres://"):
            return f"postgresql+psycopg://{normalized[len('postgres://'):]}"
        if normalized.startswith("postgresql://"):
            return f"postgresql+psycopg://{normalized[len('postgresql://'):]}"
        return normalized

    @field_validator("supabase_url")
    @classmethod
    def normalize_supabase_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized.rstrip("/") or None

    @field_validator("supabase_public_key")
    @classmethod
    def normalize_supabase_public_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("supabase_service_role_key", "supabase_storage_bucket")
    @classmethod
    def normalize_storage_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("ai_model_name", "ai_model_cache_dir")
    @classmethod
    def normalize_ai_string(cls, value: str) -> str:
        normalized = value.strip()
        return normalized

    @field_validator("ai_model_pretrained")
    @classmethod
    def normalize_ai_optional_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def finalize_settings(self) -> Settings:
        if self.run_migrations_on_start is None:
            self.run_migrations_on_start = self.app_env == "local"
        if self.run_seed_on_start is None:
            self.run_seed_on_start = self.app_env == "local"
        if self.local_auth_bypass is None:
            self.local_auth_bypass = self.app_env == "local"

        missing: list[str] = []
        if self.app_env in {"staging", "production"} and not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.local_auth_bypass and not self.supabase_url:
            missing.append("SUPABASE_URL")
        if self.app_env in {"staging", "production"}:
            if not self.supabase_service_role_key:
                missing.append("SUPABASE_SERVICE_ROLE_KEY")
            if not self.supabase_storage_bucket:
                missing.append("SUPABASE_STORAGE_BUCKET")
        if missing:
            joined = ", ".join(sorted(set(missing)))
            raise ValueError(f"Missing required environment variables: {joined}")
        if self.app_env != "local" and self.local_auth_bypass:
            raise ValueError("LOCAL_AUTH_BYPASS can only be enabled when APP_ENV=local")

        if self.seed_limit <= 0:
            raise ValueError("SEED_LIMIT must be greater than zero")
        if self.ai_color_topk <= 0:
            self.ai_color_topk = 2
        if self.ai_confidence_threshold <= 0 or self.ai_confidence_threshold > 1:
            self.ai_confidence_threshold = 0.6
        if (
            self.ai_subcategory_confidence_threshold <= 0
            or self.ai_subcategory_confidence_threshold > 1
        ):
            self.ai_subcategory_confidence_threshold = 0.5
        if self.ai_tag_confidence_threshold <= 0 or self.ai_tag_confidence_threshold > 1:
            self.ai_tag_confidence_threshold = 0.28
        if not self.ai_model_name:
            self.ai_model_name = "hf-hub:Marqo/marqo-fashionCLIP"
        if not self.ai_model_cache_dir:
            self.ai_model_cache_dir = "./media/.model_cache"
        if self.ai_color_mask_method not in {"grabcut", "heuristic"}:
            self.ai_color_mask_method = "grabcut"
        if self.ai_color_min_foreground_pixels <= 0:
            self.ai_color_min_foreground_pixels = 3000
        if self.ai_job_max_attempts <= 0:
            self.ai_job_max_attempts = 3
        if self.ai_job_poll_interval_seconds <= 0:
            self.ai_job_poll_interval_seconds = 0.5
        if self.ai_job_stale_after_seconds <= 0:
            self.ai_job_stale_after_seconds = 300
        if self.supabase_http_timeout_seconds <= 0:
            self.supabase_http_timeout_seconds = 15.0
        if self.supabase_signed_url_ttl_seconds <= 0:
            self.supabase_signed_url_ttl_seconds = 3600
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return origins or ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def is_secure_env(self) -> bool:
        return self.app_env in {"staging", "production"}

    @property
    def is_local_env(self) -> bool:
        return self.app_env == "local"

    @property
    def local_auth_bypass_enabled(self) -> bool:
        return self.is_local_env and bool(self.local_auth_bypass)

    @property
    def is_supabase_auth_configured(self) -> bool:
        return bool(self.supabase_url)

    @property
    def is_supabase_storage_configured(self) -> bool:
        return bool(
            self.supabase_url
            and self.supabase_service_role_key
            and self.supabase_storage_bucket
        )

    @property
    def supabase_issuer(self) -> str | None:
        if not self.supabase_url:
            return None
        return f"{self.supabase_url}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str | None:
        issuer = self.supabase_issuer
        if not issuer:
            return None
        return f"{issuer}/.well-known/jwks.json"

    @property
    def supabase_userinfo_url(self) -> str | None:
        issuer = self.supabase_issuer
        if not issuer:
            return None
        return f"{issuer}/user"

    @property
    def media_root_path(self) -> Path:
        return Path(self.media_root).expanduser().resolve()

    @property
    def ai_model_cache_dir_path(self) -> Path:
        return Path(self.ai_model_cache_dir).expanduser().resolve()

    @property
    def seed_on_start(self) -> bool:
        """Backward-compatible alias for older seed helpers."""
        return bool(self.run_seed_on_start)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
