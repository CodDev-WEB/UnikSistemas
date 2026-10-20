from __future__ import annotations

import argparse
import os
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath


DEFAULT_UPLOADS_PATH = Path("/var/lib/unik/uploads")


def uploads_path() -> Path:
    return Path(os.environ.get("UPLOADS_PATH", str(DEFAULT_UPLOADS_PATH))).resolve()


def make_backup(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w:gz") as archive:
        archive.add(root, arcname="uploads", recursive=True)


def validated_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    if not members:
        raise ValueError("O arquivo de backup não contém entradas.")

    seen: set[str] = set()
    has_root = False
    for member in members:
        name = member.name
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or path.is_absolute()
            or ".." in path.parts
            or not path.parts
            or path.parts[0] != "uploads"
        ):
            raise ValueError(f"Caminho inseguro no arquivo: {name!r}")
        if name in seen:
            raise ValueError(f"Entrada duplicada no arquivo: {name!r}")
        seen.add(name)
        if not (member.isdir() or member.isfile()):
            raise ValueError(f"Tipo de entrada não permitido no arquivo: {name!r}")
        if name == "uploads":
            if not member.isdir():
                raise ValueError("A raiz do volume no arquivo deve ser um diretório.")
            has_root = True

    if not has_root:
        raise ValueError("O arquivo de backup não contém a raiz uploads/.")
    return members


def inspect_backup(path: Path) -> list[tarfile.TarInfo]:
    with tarfile.open(path, mode="r:gz") as archive:
        return validated_members(archive)


def restore_backup(root: Path, path: Path) -> None:
    # Validate every member before deleting any current file.
    members = inspect_backup(path)
    root.mkdir(parents=True, exist_ok=True)
    for child in root.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()

    with tarfile.open(path, mode="r:gz") as archive:
        archive.extractall(path=root.parent, members=members, filter="data")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup e restauração segura do volume de documentos.")
    parser.add_argument("action", choices=("backup", "check", "restore"))
    parser.add_argument("archive", nargs="?", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "backup":
            if args.archive is not None:
                parser.error("A ação backup grava o arquivo compactado na saída padrão e não recebe caminho.")
            make_backup(uploads_path())
        else:
            if args.archive is None:
                parser.error(f"A ação {args.action} exige o caminho de um arquivo .tar.gz.")
            members = inspect_backup(args.archive)
            if args.action == "restore":
                restore_backup(uploads_path(), args.archive)
            else:
                print(f"Arquivo válido: {len(members)} entradas.", file=sys.stderr)
        return 0
    except (OSError, tarfile.TarError, ValueError) as exc:
        print(f"Erro no arquivo de documentos: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
