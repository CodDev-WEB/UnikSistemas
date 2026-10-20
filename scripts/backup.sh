#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "$(readlink -f -- "$0")")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

BACKUP_ROOT="$ROOT_DIR/backups"
if [[ -n "${BACKUP_DIR:-}" ]]; then
  BACKUP_ROOT="$BACKUP_DIR"
fi
mkdir -p "$BACKUP_ROOT"
chmod 700 "$BACKUP_ROOT"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$BACKUP_ROOT/unik-$STAMP"
TEMP="$BACKUP_ROOT/.unik-$STAMP.partial"
if [[ -e "$DEST" || -e "$TEMP" ]]; then
  echo "Já existe um backup com o identificador $STAMP." >&2
  exit 1
fi
mkdir -m 700 "$TEMP"

SERVICES=(api document-scan-worker notification-worker)
RUNNING_SERVICES=()
for service in "${SERVICES[@]}"; do
  if [[ -n "$(docker compose ps --status running -q "$service")" ]]; then
    RUNNING_SERVICES+=("$service")
  fi
done

STOPPED=0
cleanup() {
  status=$?
  if (( STOPPED == 1 )) && (("${#RUNNING_SERVICES[@]}" > 0)); then
    if ! docker compose start "${RUNNING_SERVICES[@]}"; then
      echo "ATENÇÃO: não foi possível reiniciar todos os serviços parados." >&2
      (( status == 0 )) && status=1
    fi
  fi
  if (( status != 0 )); then
    rm -rf -- "$TEMP"
  fi
  exit "$status"
}
trap cleanup EXIT

echo "Parando gravações da aplicação para obter um backup consistente..."
docker compose stop "${SERVICES[@]}"
STOPPED=1

docker compose exec -T db sh -ec '
  pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null
  exec pg_dump --format=custom --no-owner --no-acl \
    --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"
' > "$TEMP/database.dump"

docker compose run --rm --no-deps -T \
  -v "$SCRIPT_DIR/archive_volume.py:/tmp/archive_volume.py:ro" \
  api python /tmp/archive_volume.py backup > "$TEMP/uploads.tar.gz"

test -s "$TEMP/database.dump"
test -s "$TEMP/uploads.tar.gz"
docker compose exec -T db sh -ec 'pg_restore --list >/dev/null' < "$TEMP/database.dump"
gzip -t "$TEMP/uploads.tar.gz"
docker compose run --rm --no-deps -T \
  -v "$SCRIPT_DIR/archive_volume.py:/tmp/archive_volume.py:ro" \
  -v "$TEMP/uploads.tar.gz:/tmp/uploads.tar.gz:ro" \
  api python /tmp/archive_volume.py check /tmp/uploads.tar.gz

{
  printf 'created_at_utc=%s\n' "$STAMP"
  printf 'database_service=db\n'
  printf 'database_format=pg_dump-custom\n'
  printf 'uploads_archive=uploads.tar.gz\n'
  printf 'notes=Keep this directory private; it contains confidential client data.\n'
} > "$TEMP/MANIFEST.txt"
(
  cd "$TEMP"
  sha256sum database.dump uploads.tar.gz > SHA256SUMS
)
chmod 600 "$TEMP/database.dump" "$TEMP/uploads.tar.gz" "$TEMP/MANIFEST.txt" "$TEMP/SHA256SUMS"

mv -- "$TEMP" "$DEST"
echo "Backup criado e verificado: $DEST"
echo "Guarde uma cópia criptografada fora deste servidor e teste a restauração em homologação."
