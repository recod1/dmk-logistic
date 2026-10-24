#!/usr/bin/env bash
# Per-boot startup for the dmk-logistic dev environment.
# Starts Postgres, ensures the database/role exist, and applies migrations.
# Idempotent and safe to re-run.
set -euo pipefail

WORKSPACE="${WORKSPACE:-/workspace}"
cd "$WORKSPACE"

# shellcheck disable=SC1091
source "$WORKSPACE/.cursor/env.sh"

mkdir -p "$WORKSPACE/.cursor/run" "$MOBILE_UPLOAD_ROOT"

echo "==> Ensuring Postgres cluster is running..."
if ! sudo pg_lsclusters -h 2>/dev/null | awk '{print $4}' | grep -q online; then
  sudo pg_ctlcluster 16 main start || true
fi
# Wait for Postgres to accept connections.
for _ in $(seq 1 30); do
  if sudo -u postgres pg_isready -q; then break; fi
  sleep 1
done

echo "==> Ensuring role password and database exist..."
sudo -u postgres psql -qc "ALTER USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';" >/dev/null
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB}'" | grep -q 1; then
  sudo -u postgres psql -qc "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};" >/dev/null
fi

echo "==> Applying Alembic migrations..."
alembic upgrade head

echo "==> start.sh complete. Postgres is ready on localhost:5432."
