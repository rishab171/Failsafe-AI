#!/bin/sh
set -e

mkdir -p /data
chown -R app:app /data

exec su app -s /bin/sh -c 'uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}'
