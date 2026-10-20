from functools import lru_cache
from typing import Literal

from pydantic import EmailStr, Field, model_validator
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
    cors_origins: list[str] = Field(default_factory=list)
    document_storage_path: str = "/var/lib/unik/uploads"
    email_notifications_enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: EmailStr | None = None
    smtp_use_ssl: bool = False
    smtp_starttls: bool = True
    app_base_url: str | None = None
    notification_timezone: str = "America/Santarem"

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.email_notifications_enabled:
            if not self.smtp_host or not self.smtp_from_email:
                raise ValueError("E-mail está habilitado, mas SMTP_HOST e SMTP_FROM_EMAIL não foram configurados.")
            if self.smtp_use_ssl and self.smtp_starttls:
                raise ValueError("SMTP_USE_SSL e SMTP_STARTTLS não podem estar habilitados juntos.")
        if self.app_env == "production":
            if len(self.secret_key) < 32 or self.secret_key.startswith("dev-only"):
                raise ValueError("Em produção, SECRET_KEY deve ter pelo menos 32 caracteres aleatórios.")
            if self.bootstrap_token and len(self.bootstrap_token) < 32:
                raise ValueError("Em produção, BOOTSTRAP_TOKEN deve ter pelo menos 32 caracteres.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
