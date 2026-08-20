#!/bin/sh
set -eu
mkdir -p "${DATA_DIR:-/data}/exports"

cmd="${1:-web}"
shift || true

case "$cmd" in
  web)
    exec gunicorn --bind "0.0.0.0:${PORT:-8000}" --workers 1 --threads 4 --timeout 120 app:app
    ;;
  daily)
    exec python jobs/daily.py "$@"
    ;;
  *)
    exec "$cmd" "$@"
    ;;
esac
