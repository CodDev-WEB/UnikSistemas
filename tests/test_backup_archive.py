from __future__ import annotations

import os
import subprocess
import sys
import tarfile
from io import BytesIO
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "archive_volume.py"


def run_helper(
    action: str,
    uploads: Path,
    archive: Path | None = None,
) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env["UPLOADS_PATH"] = str(uploads)
    command = [sys.executable, str(SCRIPT), action]
    if archive is not None:
        command.append(str(archive))
    return subprocess.run(
        command,
        capture_output=True,
        env=env,
        check=False,
    )


def make_tar(entries: list[tuple[tarfile.TarInfo, bytes]]) -> bytes:
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for entry, content in entries:
            entry.size = len(content) if entry.isfile() else 0
            archive.addfile(entry, BytesIO(content) if entry.isfile() else None)
    return buffer.getvalue()


def test_archive_round_trip_replaces_volume_contents(tmp_path: Path):
    source = tmp_path / "source"
    nested = source / "client-42"
    nested.mkdir(parents=True)
    (nested / "document.pdf").write_bytes(b"sample document")
    (source / "metadata.txt").write_text("kept in upload volume", encoding="utf-8")

    backed_up = run_helper("backup", source)
    assert backed_up.returncode == 0, backed_up.stderr.decode()
    archive_file = tmp_path / "uploads.tar.gz"
    archive_file.write_bytes(backed_up.stdout)

    check = run_helper("check", source, archive_file)
    assert check.returncode == 0, check.stderr.decode()

    destination = tmp_path / "destination-root" / "uploads"
    destination.mkdir(parents=True)
    (destination / "stale.txt").write_text("must be removed", encoding="utf-8")
    restored = run_helper("restore", destination, archive_file)
    assert restored.returncode == 0, restored.stderr.decode()
    assert not (destination / "stale.txt").exists()
    assert (destination / "client-42" / "document.pdf").read_bytes() == b"sample document"
    assert (destination / "metadata.txt").read_text(encoding="utf-8") == "kept in upload volume"


def test_restore_rejects_path_traversal_before_clearing_current_files(tmp_path: Path):
    destination = tmp_path / "destination-root" / "uploads"
    destination.mkdir(parents=True)
    sentinel = destination / "keep.txt"
    sentinel.write_text("current data", encoding="utf-8")
    escaped = tmp_path / "escaped.txt"

    traversal = tarfile.TarInfo("uploads/../../escaped.txt")
    archive_file = tmp_path / "malicious.tar.gz"
    archive_file.write_bytes(make_tar([(traversal, b"bad")]))

    restored = run_helper("restore", destination, archive_file)
    assert restored.returncode != 0
    assert sentinel.read_text(encoding="utf-8") == "current data"
    assert not escaped.exists()


def test_restore_rejects_links_before_clearing_current_files(tmp_path: Path):
    destination = tmp_path / "destination-root" / "uploads"
    destination.mkdir(parents=True)
    sentinel = destination / "keep.txt"
    sentinel.write_text("current data", encoding="utf-8")

    link = tarfile.TarInfo("uploads/payload-link")
    link.type = tarfile.SYMTYPE
    link.linkname = "../../outside"
    archive_file = tmp_path / "link.tar.gz"
    archive_file.write_bytes(make_tar([(link, b"")]))

    restored = run_helper("restore", destination, archive_file)
    assert restored.returncode != 0
    assert sentinel.read_text(encoding="utf-8") == "current data"
