from __future__ import annotations

import re
import socket
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

CHUNK_SIZE = 64 * 1024
MAX_REPLY_BYTES = 4096


class AntivirusError(RuntimeError):
    """Scanner unavailable or unable to return a trustworthy verdict."""


def scan_bytes(content: bytes, host: str, port: int, timeout: int) -> str:
    """Stream bytes to clamd using INSTREAM; fail closed for every unknown reply."""
    if not host or not host.strip():
        raise AntivirusError("ANTIVIRUS_HOST não foi configurado.")
    if not content:
        raise AntivirusError("Não é possível analisar um arquivo vazio.")

    try:
        with socket.create_connection((host, port), timeout=timeout) as client:
            client.settimeout(timeout)
            client.sendall(b"zINSTREAM\0")
            for offset in range(0, len(content), CHUNK_SIZE):
                chunk = content[offset : offset + CHUNK_SIZE]
                client.sendall(struct.pack("!I", len(chunk)))
                client.sendall(chunk)
            client.sendall(struct.pack("!I", 0))

            response = bytearray()
            while b"\0" not in response and b"\n" not in response:
                chunk = client.recv(1024)
                if not chunk:
                    raise AntivirusError("O ClamAV encerrou a conexão antes de retornar um resultado.")
                response.extend(chunk)
                if len(response) > MAX_REPLY_BYTES:
                    raise AntivirusError("Resposta do ClamAV excedeu o limite esperado.")
    except AntivirusError:
        raise
    except OSError as exc:
        raise AntivirusError("Não foi possível concluir a análise antimalware.") from exc

    reply = response.decode("utf-8", errors="replace").rstrip("\0\r\n")
    if " FOUND" in reply:
        return "infected"
    if reply.endswith(": OK"):
        return "clean"
    if " ERROR" in reply or reply.endswith("ERROR"):
        raise AntivirusError("O ClamAV não conseguiu analisar o arquivo.")
    raise AntivirusError("Resposta inesperada do ClamAV; arquivo mantido em quarentena.")


@dataclass(frozen=True)
class ClamAVInfo:
    engine_version: str
    database_version: str
    database_date: datetime


def query_clamd(command: bytes, host: str, port: int, timeout: int) -> str:
    """Run one bounded clamd command and read its null-terminated response."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as client:
            client.settimeout(timeout)
            client.sendall(b"z" + command + b"\\0")
            response = bytearray()
            while b"\\0" not in response and b"\\n" not in response:
                chunk = client.recv(1024)
                if not chunk:
                    raise AntivirusError("O ClamAV encerrou a conexão antes de responder.")
                response.extend(chunk)
                if len(response) > MAX_REPLY_BYTES:
                    raise AntivirusError("Resposta do ClamAV excedeu o limite esperado.")
    except AntivirusError:
        raise
    except OSError as exc:
        raise AntivirusError("Não foi possível consultar o ClamAV.") from exc
    reply = response.decode("utf-8", errors="replace").rstrip("\\0\\r\\n")
    if not reply or "ERROR" in reply.upper() or "COMMAND UNAVAILABLE" in reply.upper():
        raise AntivirusError("O ClamAV não retornou uma resposta de estado válida.")
    return reply


def parse_clamd_version(reply: str) -> ClamAVInfo:
    """Parse clamd VERSION output: engine/db-version/database-build-date."""
    match = re.fullmatch(
        r"ClamAV\\s+([^/\\s]+)/([0-9]+)/([A-Za-z]{3} [A-Za-z]{3} +[0-9]{1,2} "
        r"[0-9]{2}:[0-9]{2}:[0-9]{2} [0-9]{4})",
        reply.strip(),
    )
    if match is None:
        raise AntivirusError("Não foi possível validar a versão e a data das assinaturas do ClamAV.")
    try:
        build_date = datetime.strptime(match.group(3), "%a %b %d %H:%M:%S %Y").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise AntivirusError("A data das assinaturas do ClamAV é inválida.") from exc
    return ClamAVInfo(
        engine_version=match.group(1),
        database_version=match.group(2),
        database_date=build_date,
    )


def get_clamav_info(host: str, port: int, timeout: int) -> ClamAVInfo:
    reply = query_clamd(b"VERSION", host, port, timeout)
    return parse_clamd_version(reply)


def signature_status(
    database_date: datetime,
    now: datetime,
    max_age_hours: int,
) -> tuple[str, str | None]:
    """Return healthy only when the signature build time can be verified and is fresh."""
    current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    built = database_date if database_date.tzinfo else database_date.replace(tzinfo=timezone.utc)
    age = current.astimezone(timezone.utc) - built.astimezone(timezone.utc)
    if age < timedelta(hours=-6):
        return "signatures_stale", "A data do banco de assinaturas está no futuro e não pode ser validada."
    if age > timedelta(hours=max_age_hours):
        return "signatures_stale", (
            f"O banco de assinaturas excede o limite de {max_age_hours} horas."
        )
    return "healthy", None
