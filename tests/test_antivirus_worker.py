from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient

from app import document_scan_worker as worker
from app.antivirus import AntivirusError, ClamAVInfo
from app.antivirus_ops import refresh_antivirus_health
from app.models import Notification


def _provision(client: TestClient, slug: str, email: str) -> None:
    response = client.post(
        "/api/v1/setup/tenants",
        headers={"X-Bootstrap-Token": "test-bootstrap-token-with-more-than-thirty-two"},
        json={
            "tenant_name": f"Escritório {slug}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Responsável Contábil",
            "owner_password": "Senha-Forte-Teste-2026",
        },
    )
    assert response.status_code == 201, response.text


def _login(client: TestClient, slug: str, email: str) -> str:
    response = client.post(
        "/api/v1/auth/token",
        json={
            "tenant_slug": slug,
            "email": email,
            "password": "Senha-Forte-Teste-2026",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.mark.parametrize(
    ("scenario", "expected_status", "should_scan"),
    [
        ("unavailable", "unavailable", False),
        ("stale", "signatures_stale", False),
        ("healthy", "healthy", True),
    ],
)
def test_antivirus_worker_blocks_queue_until_scanner_is_healthy(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    expected_status: str,
    should_scan: bool,
):
    _provision(client, "scanner-a", "owner-a@example.com")
    owner_a = _login(client, "scanner-a", "owner-a@example.com")
    admin_response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {owner_a}"},
        json={
            "email": "admin-a@example.com",
            "full_name": "Admin do Escritório A",
            "password": "Senha-Forte-Teste-2026",
            "role": "admin",
        },
    )
    assert admin_response.status_code == 201, admin_response.text
    _provision(client, "scanner-b", "owner-b@example.com")

    settings = client.app.state.test_settings
    session_factory = client.app.state.test_sessionmaker
    monkeypatch.setattr(worker, "SessionLocal", session_factory)

    now = datetime.now(UTC)

    def probe(_host: str, _port: int, _timeout: int) -> ClamAVInfo:
        if scenario == "unavailable":
            raise AntivirusError("scanner unavailable in test")
        age = timedelta(hours=100) if scenario == "stale" else timedelta(hours=1)
        return ClamAVInfo(
            engine_version="1.5.1",
            database_version="28766",
            database_date=now - age,
        )

    monkeypatch.setattr(
        worker,
        "refresh_antivirus_health",
        lambda db, active_settings: refresh_antivirus_health(
            db,
            active_settings,
            probe=probe,
            now=now,
        ),
    )

    scan_calls: list[bool] = []

    def fake_process_pending_scans(db, active_settings):
        scan_calls.append(True)
        return {"scanned": 1, "clean": 1, "infected": 0, "failed": 0}

    monkeypatch.setattr(worker, "process_pending_scans", fake_process_pending_scans)

    result = worker.run_once(settings)

    assert result["scanner_status"] == expected_status
    assert bool(scan_calls) is should_scan
    assert result["scanned"] == (1 if should_scan else 0)
    assert result["quarantine_purged"] == 0

    with session_factory() as db:
        events = db.scalars(
            select(Notification).where(Notification.event_type == "antivirus_alert")
        ).all()
        expected_alerts = 0 if should_scan else 3
        assert len(events) == expected_alerts
        assert len({(event.tenant_id, event.recipient_user_id) for event in events}) == expected_alerts
        if events:
            assert {event.title for event in events} == {
                "Scanner antimalware indisponível"
                if scenario == "unavailable"
                else "Assinaturas antimalware desatualizadas"
            }
