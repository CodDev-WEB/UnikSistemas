#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "$(readlink -f -- "$0")")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

if [[ $# -ne 1 ]]; then
  echo "Uso: bash scripts/restore-drill.sh CAMINHO_DO_DIRETORIO_DE_BACKUP" >&2
  exit 2
fi

BACKUP_DIR="$(cd -- "$1" && pwd)"
for file in database.dump uploads.tar.gz MANIFEST.txt SHA256SUMS; do
  if [[ ! -f "$BACKUP_DIR/$file" || -L "$BACKUP_DIR/$file" ]]; then
    echo "Backup incompleto ou arquivo não regular: $file" >&2
    exit 2
  fi
done

# Accept only the two files produced by backup.sh. Never let an untrusted
# checksum manifest make the verifier read arbitrary paths.
python - "$BACKUP_DIR" <<'PY'
import hashlib
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
expected = {"database.dump", "uploads.tar.gz"}
lines = (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
checksums = {}
for line in lines:
    match = re.fullmatch(r"([0-9a-fA-F]{64})  (database\.dump|uploads\.tar\.gz)", line)
    if match is None or match.group(2) in checksums:
        raise SystemExit("SHA256SUMS inválido: somente database.dump e uploads.tar.gz são permitidos.")
    checksums[match.group(2)] = match.group(1).lower()
if set(checksums) != expected:
    raise SystemExit("SHA256SUMS precisa conter exatamente database.dump e uploads.tar.gz.")
for filename, expected_hash in checksums.items():
    digest = hashlib.sha256()
    with (root / filename).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_hash:
        raise SystemExit(f"Checksum inválido: {filename}")
print("Checksums do backup válidos.")
PY

gzip -t "$BACKUP_DIR/uploads.tar.gz"
docker compose exec -T db sh -ec 'pg_restore --list >/dev/null' < "$BACKUP_DIR/database.dump"
docker compose run --rm --no-deps -T \
  -v "$SCRIPT_DIR/archive_volume.py:/tmp/archive_volume.py:ro" \
  -v "$BACKUP_DIR/uploads.tar.gz:/tmp/uploads.tar.gz:ro" \
  api python /tmp/archive_volume.py check /tmp/uploads.tar.gz

APP_ENV_IN_CONTAINER="$(docker compose exec -T api python -c 'from app.config import get_settings; print(get_settings().app_env)')"
if [[ "$APP_ENV_IN_CONTAINER" != "staging" ]]; then
  echo "Bloqueado: o ensaio só pode ser executado quando APP_ENV=staging (atual: $APP_ENV_IN_CONTAINER)." >&2
  exit 2
fi

echo
echo "ENSAIO DE RESTAURAÇÃO ISOLADO"
echo "Backup: $BACKUP_DIR"
echo "O procedimento cria um banco temporário e um volume Docker temporário."
echo "O banco e o volume atuais da aplicação não serão substituídos."
read -r -p 'Digite RESTORE-UNIK-DRILL para continuar: ' confirmation
if [[ "$confirmation" != "RESTORE-UNIK-DRILL" ]]; then
  echo "Ensaio cancelado; nenhum recurso temporário foi criado."
  exit 1
fi

STAMP="$(date -u +%Y%m%d%H%M%S)"
DRILL_DB="unik_restore_drill_${STAMP}_$$"
DRILL_VOLUME="unik_restore_drill_${STAMP}_$$"
DRILL_DB_CREATED=0
DRILL_VOLUME_CREATED=0

cleanup() {
  local status=$?
  trap - EXIT
  if (( DRILL_DB_CREATED == 1 )); then
    if ! docker compose exec -T -e DRILL_DB="$DRILL_DB" db sh -ec \
      'dropdb --if-exists --force --username="$POSTGRES_USER" --maintenance-db=postgres "$DRILL_DB"' >/dev/null; then
      echo "ATENÇÃO: não foi possível remover o banco temporário $DRILL_DB." >&2
      status=1
    fi
  fi
  if (( DRILL_VOLUME_CREATED == 1 )); then
    if ! docker volume rm "$DRILL_VOLUME" >/dev/null; then
      echo "ATENÇÃO: não foi possível remover o volume temporário $DRILL_VOLUME." >&2
      status=1
    fi
  fi
  if (( status == 0 )); then
    echo "Ensaio concluído; banco e volume temporários removidos."
  else
    echo "O ensaio falhou. Consulte a mensagem acima; recursos temporários podem exigir limpeza manual." >&2
  fi
  exit "$status"
}
trap cleanup EXIT

docker compose exec -T -e DRILL_DB="$DRILL_DB" db sh -ec \
  'createdb --username="$POSTGRES_USER" --maintenance-db=postgres "$DRILL_DB"'
DRILL_DB_CREATED=1

docker compose exec -T -e DRILL_DB="$DRILL_DB" db sh -ec \
  'exec pg_restore --exit-on-error --no-owner --no-acl --username="$POSTGRES_USER" --dbname="$DRILL_DB"' \
  < "$BACKUP_DIR/database.dump"

docker volume create "$DRILL_VOLUME" >/dev/null
DRILL_VOLUME_CREATED=1

docker compose run --rm --no-deps -T --user 0:0 \
  -e UPLOADS_PATH=/tmp/restore-drill/uploads \
  -v "$DRILL_VOLUME:/tmp/restore-drill" \
  -v "$SCRIPT_DIR/archive_volume.py:/tmp/archive_volume.py:ro" \
  -v "$BACKUP_DIR/uploads.tar.gz:/tmp/uploads.tar.gz:ro" \
  api python /tmp/archive_volume.py restore /tmp/uploads.tar.gz

read -r -d '' VALIDATE_RESTORED_DATABASE <<'PY' || true
import json
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

base_url = make_url(os.environ["DATABASE_URL"])
if base_url.drivername != "postgresql+psycopg":
    raise SystemExit("O ensaio exige DATABASE_URL com PostgreSQL + psycopg.")
engine = create_engine(base_url.set(database=os.environ["DRILL_DB"]))
required_tables = {"alembic_version", "tenants", "users", "clients", "client_documents"}
with engine.connect() as connection:
    tables = set(inspect(connection).get_table_names())
    missing_tables = sorted(required_tables - tables)
    if missing_tables:
        raise SystemExit("Tabelas ausentes na restauração: " + ", ".join(missing_tables))
    revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    if not revision:
        raise SystemExit("A restauração não contém uma revisão Alembic válida.")
    table_counts = {}
    for table in ("tenants", "users", "clients", "client_tasks", "client_documents", "notifications", "audit_logs"):
        if table in tables:
            table_counts[table] = int(connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())
    documents = connection.execute(
        text("SELECT storage_key, scan_status, quarantine_purged_at FROM client_documents")
    ).all()

uploads = Path(os.environ["UPLOADS_PATH"]).resolve()
missing_payloads = []
for storage_key, scan_status, purged_at in documents:
    if purged_at is not None:
        continue
    if (
        not storage_key
        or Path(storage_key).name != storage_key
        or storage_key in {".", ".."}
        or "/" in storage_key
        or "\\" in storage_key
    ):
        missing_payloads.append("[chave inválida]")
        continue
    candidates = (uploads / storage_key, uploads / "quarantine" / storage_key, uploads / "clean" / storage_key)
    if not any(candidate.is_file() for candidate in candidates):
        missing_payloads.append(storage_key)
if missing_payloads:
    sample = ", ".join(missing_payloads[:10])
    raise SystemExit(f"{len(missing_payloads)} documento(s) sem arquivo correspondente no volume restaurado: {sample}")

print(json.dumps({
    "revision": revision,
    "table_counts": table_counts,
    "document_records": len(documents),
    "document_payloads_missing": 0,
}, ensure_ascii=False))
engine.dispose()
PY

docker compose run --rm --no-deps -T --user 0:0 \
  -e DRILL_DB="$DRILL_DB" \
  -e UPLOADS_PATH=/tmp/restore-drill/uploads \
  -v "$DRILL_VOLUME:/tmp/restore-drill:ro" \
  api python -c "$VALIDATE_RESTORED_DATABASE"

echo "Verificação concluída: o dump foi restaurado em banco isolado e os metadados dos documentos foram comparados com os arquivos recuperados."
