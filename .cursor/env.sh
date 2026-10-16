#!/usr/bin/env bash
# Shared environment variables for the dmk-logistic dev environment.
# Sourced by install.sh, start.sh and the terminal commands.

export WORKSPACE="${WORKSPACE:-/workspace}"

# --- Postgres / new mobile stack ---
export POSTGRES_DB="${POSTGRES_DB:-dmk_logistic}"
export POSTGRES_USER="${POSTGRES_USER:-postgres}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
export POSTGRES_DSN="${POSTGRES_DSN:-postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}}"
export DATABASE_URL="${DATABASE_URL:-$POSTGRES_DSN}"

# --- JWT auth ---
export JWT_SECRET="${JWT_SECRET:-dev-secret-change-me}"
export JWT_ALGORITHM="${JWT_ALGORITHM:-HS256}"
export JWT_EXPIRE_MINUTES="${JWT_EXPIRE_MINUTES:-10080}"

# --- Demo bootstrap user (login: driver / driver123) ---
export BOOTSTRAP_DEMO_USER="${BOOTSTRAP_DEMO_USER:-1}"
export DEMO_LOGIN="${DEMO_LOGIN:-driver}"
export DEMO_PASSWORD="${DEMO_PASSWORD:-driver123}"
export DEMO_ROLE="${DEMO_ROLE:-driver}"

# --- Mobile uploads dir ---
export MOBILE_UPLOAD_ROOT="${MOBILE_UPLOAD_ROOT:-$WORKSPACE/data/mobile_uploads}"

# Activate the Python virtualenv when present.
if [ -f "$WORKSPACE/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$WORKSPACE/.venv/bin/activate"
fi
