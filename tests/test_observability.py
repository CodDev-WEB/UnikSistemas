from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.models import AntivirusHealth


def test_metrics_token_is_disabled_when_blank_and_requires_reasonable_length():
    assert Settings(app_env="test", metrics_token="").metrics_token is None
    with pytest.raises(ValidationError, match="METRICS_TOKEN"):
        Settings(app_env="test", metrics_token="short")


def test_metrics_endpoint_is_disabled_by_default(client):
    response = client.get("/metrics")
    assert response.status_code == 404


def test_metrics_endpoint_requires_bearer_token_and_reports_aggregate_health(client):
    token = "metrics-token-for-test-use-only-2026"
    client.app.state.test_settings.metrics_token = token

    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong-token"}).status_code == 401

    now = datetime.now(UTC)
    with client.app.state.test_sessionmaker() as db:
        db.add(
            AntivirusHealth(
                id="clamav",
                status="healthy",
                checked_at=now,
                last_success_at=now,
                signature_database_version="28765",
                signature_database_date=now - timedelta(hours=2),
            )
        )
        db.commit()

    response = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    assert response.headers["cache-control"] == "no-store"
    assert 'unik_antivirus_health_status{status="healthy"} 1' in response.text
    assert 'unik_antivirus_health_status{status="unavailable"} 0' in response.text
    assert "unik_antivirus_signature_database_known 1" in response.text
    assert 'unik_documents_scan_status_total{status="pending"} 0' in response.text
    assert 'unik_notification_email_status_total{status="failed"} 0' in response.text
    assert "signature_database_version" not in response.text
    assert "28765" not in response.text
    assert "metrics-token" not in response.text
