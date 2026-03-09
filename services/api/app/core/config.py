"""Application configuration management."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
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

UploadMode = Literal["s3", "local"]


class Settings(BaseSettings):
    """Central application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=ENV_FILES, env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "staging", "production"] = Field(default="local", alias="APP_ENV")
    api_key: str | None = Field(default=None, alias="API_KEY")
    database_url: str = Field(..., alias="DATABASE_URL")
    aws_region: str | None = Field(default=None, alias="AWS_REGION")
    s3_bucket_name: str | None = Field(default=None, alias="S3_BUCKET_NAME")
    cors_origins: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")

    upload_mode: UploadMode | None = Field(default=None, alias="UPLOAD_MODE")
    media_root: str = Field(default="./media", alias="MEDIA_ROOT")
    media_url_path: str = Field(default="/media", alias="MEDIA_URL_PATH")
    media_max_upload_size: int = Field(default=15 * 1024 * 1024, alias="MEDIA_MAX_UPLOAD_SIZE")
    seed_on_start: bool | None = Field(default=None, alias="SEED_ON_START")
    seed_limit: int = Field(default=25, alias="SEED_LIMIT")
    seed_key: str = Field(default="local-seed-v1", alias="SEED_KEY")
    ai_enable_classifier: bool = Field(default=True, alias="AI_ENABLE_CLASSIFIER")
    ai_device: str = Field(default="cpu", alias="AI_DEVICE")
    ai_onnx: bool = Field(default=False, alias="AI_ONNX")
    ai_confidence_threshold: float = Field(default=0.6, alias="AI_CONFIDENCE_THRESHOLD")
    ai_subcategory_confidence_threshold: float = Field(
        default=0.5,
        alias="AI_SUBCATEGORY_CONFIDENCE_THRESHOLD",
    )
    ai_color_use_mask: bool = Field(default=True, alias="AI_COLOR_USE_MASK")
    ai_color_mask_method: Literal["grabcut", "heuristic"] = Field(
        default="grabcut", alias="AI_COLOR_MASK_METHOD"
    )
    ai_color_min_foreground_pixels: int = Field(
        default=3000, alias="AI_COLOR_MIN_FOREGROUND_PIXELS"
    )
    ai_color_topk: int = Field(default=2, alias="AI_COLOR_TOPK")
    ai_onnx_model_path: str | None = Field(default=None, alias="AI_ONNX_MODEL_PATH")

    @field_validator("cors_origins")
    @classmethod
    def normalize_origins(cls, value: str) -> str:
        return value or ""

    @field_validator("media_url_path")
    @classmethod
    def normalize_media_url(cls, value: str) -> str:
        if not value:
            return "/media"
        return value if value.startswith("/") else f"/{value}"

    @model_validator(mode="after")
    def finalize_upload_mode(self) -> Settings:
        if self.upload_mode is None:
            self.upload_mode = "s3" if self.aws_region and self.s3_bucket_name else "local"

        if self.upload_mode == "s3" and not (self.aws_region and self.s3_bucket_name):
            raise ValueError("S3 upload mode requires AWS_REGION and S3_BUCKET_NAME to be set")

        if self.app_env in {"staging", "production"}:
            missing: list[str] = []
            if not self.api_key:
                missing.append("API_KEY")
            if self.upload_mode == "s3":
                if not self.aws_region:
                    missing.append("AWS_REGION")
                if not self.s3_bucket_name:
                    missing.append("S3_BUCKET_NAME")
            if missing:
                joined = ", ".join(missing)
                raise ValueError(f"Missing required environment variables: {joined}")

        if self.seed_on_start is None:
            self.seed_on_start = self.app_env == "local"

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
        if self.ai_color_mask_method not in {"grabcut", "heuristic"}:
            self.ai_color_mask_method = "grabcut"
        if self.ai_color_min_foreground_pixels <= 0:
            self.ai_color_min_foreground_pixels = 3000
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return origins or ["http://localhost:5173"]

    @property
    def is_secure_env(self) -> bool:
        return self.app_env in {"staging", "production"}

    @property
    def media_root_path(self) -> Path:
        return Path(self.media_root).expanduser().resolve()

    @property
    def upload_mode_value(self) -> UploadMode:
        # upload_mode is guaranteed to be populated in finalize_upload_mode
        return self.upload_mode or "local"

    @property
    def is_s3_enabled(self) -> bool:
        return self.upload_mode_value == "s3"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
