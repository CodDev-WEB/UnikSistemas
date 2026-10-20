import pytest
from pydantic import ValidationError

from app.config import Settings


BASE_SETTINGS = {
    "app_env": "test",
    "secret_key": "test-secret-key-with-more-than-thirty-two-characters",
    "database_url": "sqlite://",
    "bootstrap_token": None,
}


def make_settings(**overrides) -> Settings:
    return Settings(**(BASE_SETTINGS | overrides))


def test_email_notifications_are_disabled_by_default():
    settings = make_settings()
    assert settings.email_notifications_enabled is False
    assert settings.smtp_from_email is None


def test_email_notifications_require_host_and_sender_when_enabled():
    with pytest.raises(ValidationError, match="SMTP_HOST"):
        make_settings(email_notifications_enabled=True)

    settings = make_settings(
        email_notifications_enabled=True,
        smtp_host="smtp.example.com",
        smtp_from_email="alerts@example.com",
    )
    assert settings.email_notifications_enabled is True
    assert settings.smtp_host == "smtp.example.com"


def test_smtp_ssl_and_starttls_cannot_be_enabled_together():
    with pytest.raises(ValidationError, match="não podem estar habilitados juntos"):
        make_settings(
            email_notifications_enabled=True,
            smtp_host="smtp.example.com",
            smtp_from_email="alerts@example.com",
            smtp_use_ssl=True,
            smtp_starttls=True,
        )


def test_invalid_notification_timezone_is_rejected():
    with pytest.raises(ValidationError, match="fuso IANA válido"):
        make_settings(notification_timezone="Not/A_Real_Zone")


def test_production_requires_postgresql_psycopg():
    with pytest.raises(ValidationError, match="PostgreSQL com o driver psycopg"):
        make_settings(app_env="production", secret_key="s" * 48, database_url="sqlite:///prod.db")


def test_production_rejects_default_database_password():
    with pytest.raises(ValidationError, match="pelo menos 24 caracteres"):
        make_settings(
            app_env="production",
            secret_key="s" * 48,
            database_url=(
                "postgresql+psycopg://unik:replace-with-a-long-random-password"
                "@db:5432/unik"
            ),
        )


def test_production_accepts_strong_postgresql_settings():
    settings = make_settings(
        app_env="production",
        secret_key="a-strong-production-signing-key-value-longer-than-32",
        database_url=(
            "postgresql+psycopg://unik:StrongDbPassword-Unique-2026-Long"
            "@db:5432/unik"
        ),
    )
    assert settings.app_env == "production"
    assert settings.database_url.startswith("postgresql+psycopg://")
