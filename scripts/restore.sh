#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

if [[ $# -ne 1 ]]; then
  echo "Uso: bash scripts/restore.sh CAMINHO_DO_DIRETORIO_DE_BACKUP" >&2
  exit 2
fi
BACKUP_DIR="$(cd -- "$1" && pwd)"
for file in database.dump uploads.tar.gz MANIFEST.txt SHA256SUMS; do
  if [[ ! -f "$BACKUP_DIR/$file" ]]; then
    echo "Backup incompleto: arquivo ausente: $file" >&2
    exit 2
  fi
done

(
  cd "$BACKUP_DIR"
  sha256sum --check --strict SHA256SUMS
)
gzip -t "$BACKUP_DIR/uploads.tar.gz"
docker compose exec -T db sh -ec 'pg_restore --list >/dev/null' < "$BACKUP_DIR/database.dump"
docker compose run --rm --no-deps -T \
  -v "$SCRIPT_DIR/archive_volume.py:/tmp/archive_volume.py:ro" \
  -v "$BACKUP_DIR/uploads.tar.gz:/tmp/uploads.tar.gz:ro" \
  api python /tmp/archive_volume.py check /tmp/uploads.tar.gz

echo
echo "ATENÇÃO: a restauração SUBSTITUI o banco de dados e os arquivos enviados atuais."
echo "Backup selecionado: $BACKUP_DIR"
read -r -p 'Digite RESTORE-UNIK para confirmar: ' confirmation
if [[ "$confirmation" != "RESTORE-UNIK" ]]; then
  echo "Restauração cancelada; nenhum serviço foi parado."
  exit 1
fi

SERVICES=(api document-scan-worker notification-worker)
RUNNING_SERVICES=()
for service in "${SERVICES[@]}"; do
  if [[ -n "$(docker compose ps --status running -q "$service")" ]]; then
    RUNNING_SERVICES+=("$service")
  fi
done

RESTORE_SUCCEEDED=0
cleanup() {
  status=$?
  if (( RESTORE_SUCCEEDED == 1 )); then
    if (("${#RUNNING_SERVICES[@]}" > 0)); then
      docker compose start "${RUNNING_SERVICES[@]}"
    fi
    echo "Restauração concluída. Valide login, clientes, documentos e logs antes de liberar o uso."
  else
    echo "Restauração incompleta. Por segurança, os serviços de aplicação permanecerão parados." >&2
    echo "Corrija a causa e repita a restauração a partir de um backup íntegro." >&2
  fi
  exit "$status"
}
trap cleanup EXIT

docker compose stop "${SERVICES[@]}"

docker compose exec -T db sh -ec '
  dropdb --if-exists --force --username="$POSTGRES_USER" \
    --maintenance-db=postgres "$POSTGRES_DB"
  createdb --username="$POSTGRES_USER" --owner="$POSTGRES_USER" "$POSTGRES_DB"
'
docker compose exec -T db sh -ec '
  exec pg_restore --exit-on-error --no-owner --no-acl \
    --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"
' < "$BACKUP_DIR/database.dump"

docker compose run --rm --no-deps -T \
  -v "$SCRIPT_DIR/archive_volume.py:/tmp/archive_volume.py:ro" \
  -v "$BACKUP_DIR/uploads.tar.gz:/tmp/uploads.tar.gz:ro" \
  api python /tmp/archive_volume.py restore /tmp/uploads.tar.gz

RESTORE_SUCCEEDED=1
