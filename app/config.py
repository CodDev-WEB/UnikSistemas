from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    secret_key: str = "dev-only-change-this-secret-to-a-random-value"
    database_url: str = "sqlite:///./unik.db"
    bootstrap_token: str | None = None
    access_token_expire_minutes: int = Field(default=60, ge=5, le=1440)
    cors_origins: list[str] = Field(default_factory=list)\n    document_storage_path: str = "/var/lib/unik/uploads"
    document_storage_path: str = "/var/lib/unik/uploads"

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.app_env == "production":
            if len(self.secret_key) < 32 or self.secret_key.startswith("dev-only"):
                raise ValueError("Em produção, SECRET_KEY deve ter pelo menos 32 caracteres aleatórios.")
            if self.bootstrap_token and len(self.bootstrap_token) < 32:
                raise ValueError("Em produção, BOOTSTRAP_TOKEN deve ter pelo menos 32 caracteres.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
