from datetime import UTC, datetime

from scripts import staging_readiness as readiness


def test_parse_revision_ids_extracts_alembic_current_and_heads():
    output = """
INFO [alembic.runtime.migration] Context impl PostgresqlImpl.
0008_notification_queue_age (head)
"""
    assert readiness.parse_revision_ids(output) == {"0008_notification_queue_age"}


def test_empty_or_unrecognized_revision_output_is_not_accepted():
    assert readiness.parse_revision_ids("") == set()
    assert readiness.parse_revision_ids("Database is up to date") == set()


def test_public_url_requires_https_origin_without_credentials_or_path():
    assert readiness.public_url_issues("https://staging.example.com") == []
    assert "a URL pública precisa usar HTTPS" in readiness.public_url_issues("http://staging.example.com")
    assert "não inclua usuário ou senha na URL" in readiness.public_url_issues(
        "https://user:secret@staging.example.com"
    )
    assert "informe somente a origem pública, sem caminho, query ou fragmento" in readiness.public_url_issues(
        "https://staging.example.com/app"
    )


def test_public_headers_require_hsts_and_basic_security_headers():
    missing = readiness.missing_security_headers(
        {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }
    )
    assert missing == ["Strict-Transport-Security com max-age positivo"]


def test_public_headers_accept_valid_hsts_and_browser_headers():
    missing = readiness.missing_security_headers(
        {
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }
    )
    assert missing == []


def test_health_endpoint_rejects_wrong_json_payload(monkeypatch):
    monkeypatch.setattr(
        readiness,
        "fetch_http",
        lambda *_args: (200, b'{"status":"ok"}', {}, "http://127.0.0.1:8000/health/ready"),
    )
    result = readiness.check_json_endpoint(
        "readiness",
        "http://127.0.0.1:8000/health/ready",
        {"status": "ready", "database": "ok"},
        2,
    )
    assert result.status == "FAIL"


def test_report_records_skips_and_read_only_scope():
    report = readiness.render_report(
        [
            readiness.Check("API", "PASS", "OK"),
            readiness.Check("Borda", "SKIP", "Não configurada"),
        ],
        generated_at=datetime(2026, 10, 28, tzinfo=UTC),
    )
    assert "2026-10-28T00:00:00+00:00" in report
    assert "não executa restauração" in report
    assert "| SKIP | Borda | Não configurada |" in report
