from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import EmailStr, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


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
    metrics_token: str | None = None
    access_token_expire_minutes: int = Field(default=60, ge=5, le=1440)
    cors_origins: list[str] = Field(default_factory=list)
    document_storage_path: str = "/var/lib/unik/uploads"
    antivirus_host: str = "clamav"
    antivirus_port: int = Field(default=3310, ge=1, le=65535)
    antivirus_timeout_seconds: int = Field(default=45, ge=1, le=120)
    antivirus_signature_max_age_hours: int = Field(default=72, ge=1, le=168)
    antivirus_infected_retention_days: int = Field(default=30, ge=1, le=365)
    antivirus_cleanup_interval_hours: int = Field(default=24, ge=1, le=168)
    email_notifications_enabled: bool = False
    email_queue_max_age_hours: int = Field(default=24, ge=1, le=720)
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: EmailStr | None = None
    smtp_use_ssl: bool = False
    smtp_starttls: bool = True
    app_base_url: str | None = None
    notification_timezone: str = "America/Santarem"

    @field_validator("smtp_from_email", mode="before")
    @classmethod
    def blank_smtp_sender_to_none(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value

    @field_validator("metrics_token", mode="before")
    @classmethod
    def blank_metrics_token_to_none(cls, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.metrics_token is not None and len(self.metrics_token) < 32:
            raise ValueError("METRICS_TOKEN deve ter pelo menos 32 caracteres quando configurado.")
        try:
            ZoneInfo(self.notification_timezone)
        except ZoneInfoNotFoundError:
            raise ValueError("NOTIFICATION_TIMEZONE deve ser um fuso IANA válido.") from None
        if self.email_notifications_enabled:
            if not self.smtp_host or not self.smtp_from_email:
                raise ValueError("E-mail está habilitado, mas SMTP_HOST e SMTP_FROM_EMAIL não foram configurados.")
            if self.smtp_use_ssl and self.smtp_starttls:
                raise ValueError("SMTP_USE_SSL e SMTP_STARTTLS não podem estar habilitados juntos.")
        if self.app_env == "production":
            try:
                database_url = make_url(self.database_url)
            except ArgumentError as exc:
                raise ValueError("DATABASE_URL inválida para produção.") from exc
            if database_url.drivername != "postgresql+psycopg":
                raise ValueError("Em produção, DATABASE_URL deve usar PostgreSQL com o driver psycopg.")
            db_password = database_url.password or ""
            if len(db_password) < 24 or db_password.casefold() in {
                "unik_dev_password",
                "replace-with-a-long-random-password",
                "password",
                "postgres",
                "changeme",
            }:
                raise ValueError("A senha do banco em produção deve ser aleatória e ter pelo menos 24 caracteres.")
            if len(self.secret_key) < 32 or self.secret_key.startswith("dev-only"):
                raise ValueError("Em produção, SECRET_KEY deve ter pelo menos 32 caracteres aleatórios.")
            if self.bootstrap_token and len(self.bootstrap_token) < 32:
                raise ValueError("Em produção, BOOTSTRAP_TOKEN deve ter pelo menos 32 caracteres.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
