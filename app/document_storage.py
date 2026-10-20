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
                valid = marker in names and not archive.testzip()
        except (zipfile.BadZipFile, OSError, RuntimeError):
            valid = False
    if not valid:
        raise ValueError("O conteúdo do arquivo não corresponde ao formato informado.")

    stem = raw_name.rsplit(".", 1)[0] if "." in raw_name else "documento"
    stem = re.sub(r"[\x00-\x1f\x7f]", "", stem)
    stem = re.sub(r"[^\w .()\-]", "_", stem, flags=re.UNICODE).strip(" ._-")[:200]
    clean_name = f"{stem or 'documento'}{extension}"
    return clean_name, CONTENT_TYPES[extension]


def store_document(storage_path: str, extension: str, content: bytes) -> str:
    root = Path(storage_path)
    root.mkdir(parents=True, exist_ok=True)
    storage_key = f"{uuid4()}{extension}"
    target = root / storage_key
    with target.open("xb") as file:
        file.write(content)
    return storage_key


def load_document(storage_path: str, storage_key: str) -> bytes:
    root = Path(storage_path).resolve()
    candidate = (root / storage_key).resolve()
    if candidate.parent != root or candidate.name != storage_key:
        raise FileNotFoundError("Arquivo inválido.")
    return candidate.read_bytes()


def remove_stored_document(storage_path: str, storage_key: str) -> None:
    try:
        (Path(storage_path) / storage_key).unlink(missing_ok=True)
    except OSError:
        pass
