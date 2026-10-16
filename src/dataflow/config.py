"""DataFlow centralized application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import List, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    PROJECT_NAME: str = "DataFlow"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development", alias="ENVIRONMENT")
    LOG_LEVEL: str = Field(default="INFO", alias="LOG_LEVEL")

    # Server
    HOST: str = Field(default="127.0.0.1", alias="HOST")
    PORT: int = Field(default="8000", alias="PORT")

    # CORS
    CORS_ORIGINS: Union[List[str], str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
        alias="CORS_ORIGINS",
    )

    # Database
    DATAFLOW_DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/dataflow",
        alias="DATAFLOW_DATABASE_URL",
    )
    # Optional alternative alias for standard DATABASE_URL
    DATABASE_URL: str = Field(
        default="",
        alias="DATABASE_URL",
    )

    # Storage
    DATAFLOW_STORAGE_ROOT: str = Field(
        default="./dataflow_storage",
        alias="DATAFLOW_STORAGE_ROOT",
    )

    # Operational constraints
    MAX_UPLOAD_SIZE_BYTES: int = Field(
        default=50 * 1024 * 1024,  # 50 MB
        alias="MAX_UPLOAD_SIZE_BYTES",
    )
    MAX_PREVIEW_ROWS: int = Field(
        default=100,
        alias="MAX_PREVIEW_ROWS",
    )
    MAX_VALIDATION_EXAMPLES: int = Field(
        default=20,
        alias="MAX_VALIDATION_EXAMPLES",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    def get_effective_database_url(self) -> str:
        """Resolve database URL prioritizing DATAFLOW_DATABASE_URL or DATABASE_URL."""
        url = self.DATAFLOW_DATABASE_URL or self.DATABASE_URL
        if not url:
            return "sqlite:///./dataflow.db"
        # Standardize postgres:// to postgresql+psycopg:// if user gave older format
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    def get_storage_path(self) -> Path:
        """Return resolved absolute path to storage root."""
        path = Path(self.DATAFLOW_STORAGE_ROOT).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
