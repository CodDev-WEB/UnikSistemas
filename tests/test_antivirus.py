import struct

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
