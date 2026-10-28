#!/bin/sh
set -eu

if [ -z "$GF_SECURITY_ADMIN_PASSWORD" ]; then
  echo "Defina GRAFANA_ADMIN_PASSWORD antes de ativar o perfil de monitoramento." >&2
  exit 1
fi
case "$GF_SECURITY_ADMIN_PASSWORD" in
  *????????????????????????*) ;;
  *)
    echo "GRAFANA_ADMIN_PASSWORD deve ter pelo menos 24 caracteres." >&2
    exit 1
    ;;
esac

exec /run.sh
