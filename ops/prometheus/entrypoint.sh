#!/bin/sh
set -eu
umask 077

if [ -z "$METRICS_TOKEN" ]; then
  echo "METRICS_TOKEN é obrigatório para ativar o perfil de monitoramento." >&2
  exit 1
fi
case "$METRICS_TOKEN" in
  *????????????????????????????????*) ;;
  *)
    echo "METRICS_TOKEN deve ter pelo menos 32 caracteres." >&2
    exit 1
    ;;
esac

printf '%s' "$METRICS_TOKEN" > /run/prometheus-secrets/metrics_token
unset METRICS_TOKEN
exec /bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --storage.tsdb.retention.time=15d \
  --web.listen-address=0.0.0.0:9090
