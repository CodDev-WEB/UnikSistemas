from __future__ import annotations

import re
import unicodedata
import zipfile
from io import BytesIO
from pathlib import Path, PurePosixPath
from uuid import uuid4

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_UPLOADS_PER_LINK = 5
LINK_LIFETIME_DAYS = 7
ALLOWED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".csv", ".xlsx", ".docx")
CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def validate_uploaded_document(filename: str | None, content: bytes) -> tuple[str, str]:
    if not content:
        raise ValueError("O arquivo está vazio.")
    raw_name = unicodedata.normalize("NFKC", (filename or "").replace("\\", "/").split("/")[-1])
    extension = PurePosixPath(raw_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Formato não permitido. Envie PDF, PNG, JPG, CSV, XLSX ou DOCX.")
    if len(content) > MAX_DOCUMENT_BYTES:
        raise ValueError("O arquivo ultrapassa o limite de 10 MiB.")

    valid = False
    if extension == ".pdf":
        valid = content.startswith(b"%PDF-")
    elif extension == ".png":
        valid = content.startswith(b"\x89PNG\r\n\x1a\n")
    elif extension in {".jpg", ".jpeg"}:
        valid = content.startswith(b"\xff\xd8\xff")
    elif extension == ".csv":
        valid = b"\x00" not in content
        if valid:
            try:
                content.decode("utf-8-sig")
            except UnicodeDecodeError:
                try:
                    content.decode("cp1252")
                except UnicodeDecodeError:
                    valid = False
    elif extension in {".xlsx", ".docx"}:
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                names = set(archive.namelist())
                marker = "xl/workbook.xml" if extension == ".xlsx" else "word/document.xml"
                infos = archive.infolist()
                total_unpacked_size = sum(item.file_size for item in infos)
                valid = marker in names and len(infos) <= 2000 and total_unpacked_size <= 100 * 1024 * 1024
        except (zipfile.BadZipFile, OSError, RuntimeError):
            valid = False
    if not valid:
        raise ValueError("O conteúdo do arquivo não corresponde ao formato informado.")

    stem = raw_name.rsplit(".", 1)[0] if "." in raw_name else "documento"
    stem = re.sub(r"[\x00-\x1f\x7f]", "", stem)
    stem = re.sub(r"[^\w .()\-]", "_", stem, flags=re.UNICODE).strip(" ._-")[:200]
    clean_name = f"{stem or 'documento'}{extension}"
    return clean_name, CONTENT_TYPES[extension]


def _document_path(storage_path: str, storage_key: str, area: str | None = None) -> Path:
    if not storage_key or PurePosixPath(storage_key).name != storage_key or storage_key in {".", ".."}:
        raise FileNotFoundError("Arquivo inválido.")
    if area not in {None, "quarantine", "clean"}:
        raise FileNotFoundError("Área de armazenamento inválida.")
    root = Path(storage_path).resolve()
    base = root if area is None else (root / area).resolve()
    if area is not None and base.parent != root:
        raise FileNotFoundError("Área de armazenamento inválida.")
    candidate = (base / storage_key).resolve()
    if candidate.parent != base or candidate.name != storage_key:
        raise FileNotFoundError("Arquivo inválido.")
    return candidate


def store_document(storage_path: str, extension: str, content: bytes) -> str:
    """Persist a new upload in quarantine; it is not downloadable until promoted."""
    quarantine = Path(storage_path).resolve() / "quarantine"
    quarantine.mkdir(parents=True, exist_ok=True)
    storage_key = f"{uuid4()}{extension}"
    target = _document_path(storage_path, storage_key, "quarantine")
    with target.open("xb") as file:
        file.write(content)
    return storage_key


def load_document(storage_path: str, storage_key: str, area: str | None = None) -> bytes:
    """Load from one explicit storage area, or from the legacy root when area is None."""
    return _document_path(storage_path, storage_key, area).read_bytes()


def move_document(
    storage_path: str,
    storage_key: str,
    source_area: str | None,
    destination_area: str,
) -> None:
    if destination_area not in {"quarantine", "clean"}:
        raise ValueError("Destino de armazenamento inválido.")
    source = _document_path(storage_path, storage_key, source_area)
    target = _document_path(storage_path, storage_key, destination_area)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        if target.exists():
            return
        raise FileNotFoundError("Arquivo não encontrado para movimentação.")
    if source == target:
        return
    if target.exists():
        raise FileExistsError("Já existe um arquivo com esta chave no destino.")
    source.replace(target)


def promote_document(storage_path: str, storage_key: str, source_area: str | None) -> None:
    """Move only a scanner-cleared file into the clean storage directory."""
    if source_area == "clean":
        return
    move_document(storage_path, storage_key, source_area, "clean")


def quarantine_document(storage_path: str, storage_key: str, source_area: str | None) -> None:
    """Move a file back into quarantine; safe to call when it is already there."""
    if source_area == "quarantine":
        return
    move_document(storage_path, storage_key, source_area, "quarantine")


def load_document_for_scan(storage_path: str, storage_key: str) -> tuple[bytes, str]:
    """Load quarantined data and safely re-home legacy root files before scanning."""
    try:
        return load_document(storage_path, storage_key, "quarantine"), "quarantine"
    except FileNotFoundError:
        pass
    try:
        # Older versions stored files directly under the root. Move them to quarantine
        # before the worker reads them, so an unscanned legacy file is never downloadable.
        quarantine_document(storage_path, storage_key, None)
        return load_document(storage_path, storage_key, "quarantine"), "quarantine"
    except FileNotFoundError:
        pass
    # Recovery path for a crash after promotion but before the database verdict commit.
    return load_document(storage_path, storage_key, "clean"), "clean"


def remove_stored_document(storage_path: str, storage_key: str) -> None:
    """Best-effort rollback cleanup across legacy, quarantine and clean locations."""
    for area in (None, "quarantine", "clean"):
        try:
            _document_path(storage_path, storage_key, area).unlink(missing_ok=True)
        except OSError:
            pass
