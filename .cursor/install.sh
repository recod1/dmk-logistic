#!/usr/bin/env bash
# Idempotent bootstrap for the dmk-logistic Cloud Agent dev environment.
# Installs system packages, Python deps (venv) and web deps + build.
set -euo pipefail

WORKSPACE="${WORKSPACE:-/workspace}"
cd "$WORKSPACE"

echo "==> Installing system packages (postgres, nginx, build tools)..."
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq \
  postgresql postgresql-contrib nginx \
  python3-venv python3-dev libpq-dev build-essential

echo "==> Creating Python virtualenv and installing requirements..."
if [ ! -d "$WORKSPACE/.venv" ]; then
  python3 -m venv "$WORKSPACE/.venv"
fi
# shellcheck disable=SC1091
source "$WORKSPACE/.venv/bin/activate"
pip install --upgrade pip -q
pip install -q -r requirements.txt

echo "==> Installing web (PWA) dependencies and building..."
pushd "$WORKSPACE/web" >/dev/null
npm install
npm run build
popd >/dev/null

echo "==> install.sh complete."
