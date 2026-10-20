import struct
from datetime import datetime, timedelta, timezone

import pytest

from app import antivirus


class FakeSocket:
    def __init__(self, response: bytes):
        self.response = response
        self.sent = []
        self.timeout = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def settimeout(self, timeout):
        self.timeout = timeout

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, _size):
        response = self.response
        self.response = b""
        return response


def test_clamd_instream_returns_clean_and_frames_payload(monkeypatch):
    fake = FakeSocket(b"stream: OK\0")
    monkeypatch.setattr(antivirus.socket, "create_connection", lambda address, timeout: fake)
    content = b"PDF test content"

    result = antivirus.scan_bytes(content, "clamav", 3310, 10)

    assert result == "clean"
    sent = b"".join(fake.sent)
    assert sent.startswith(b"zINSTREAM\0")
    assert struct.pack("!I", len(content)) + content in sent
    assert sent.endswith(struct.pack("!I", 0))
    assert fake.timeout == 10


def test_clamd_instream_returns_infected_when_signature_matches(monkeypatch):
    fake = FakeSocket(b"stream: Eicar-Test-Signature FOUND\0")
    monkeypatch.setattr(antivirus.socket, "create_connection", lambda address, timeout: fake)

    assert antivirus.scan_bytes(b"sample", "clamav", 3310, 10) == "infected"


def test_clamd_error_response_fails_closed(monkeypatch):
    fake = FakeSocket(b"stream: INSTREAM size limit exceeded. ERROR\0")
    monkeypatch.setattr(antivirus.socket, "create_connection", lambda address, timeout: fake)

    with pytest.raises(antivirus.AntivirusError):
        antivirus.scan_bytes(b"sample", "clamav", 3310, 10)


def test_clamd_connection_failure_fails_closed(monkeypatch):
    def fail_connect(_address, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(antivirus.socket, "create_connection", fail_connect)
    with pytest.raises(antivirus.AntivirusError):
        antivirus.scan_bytes(b"sample", "clamav", 3310, 1)


def test_clamd_version_parser_extracts_signature_database_build_date():
    info = antivirus.parse_clamd_version("ClamAV 1.5.1/28765/Tue Oct 20 10:30:00 2026")

    assert info.engine_version == "1.5.1"
    assert info.database_version == "28765"
    assert info.database_date == datetime(2026, 10, 20, 10, 30, tzinfo=timezone.utc)


def test_clamd_version_parser_rejects_unverifiable_signature_date():
    with pytest.raises(antivirus.AntivirusError):
        antivirus.parse_clamd_version("ClamAV 1.5.1/28765/UNKNOWN DATE")


def test_signature_freshness_is_strict_and_marks_old_or_future_dates_stale():
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)

    assert antivirus.signature_status(now - timedelta(hours=12), now, 72) == ("healthy", None)
    stale_status, message = antivirus.signature_status(now - timedelta(hours=73), now, 72)
    assert stale_status == "signatures_stale"
    assert "72 horas" in message
    future_status, _ = antivirus.signature_status(now + timedelta(days=1), now, 72)
    assert future_status == "signatures_stale"
