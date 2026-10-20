from __future__ import annotations

import socket
import struct

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
