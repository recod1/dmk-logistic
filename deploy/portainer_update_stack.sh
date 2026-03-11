#!/usr/bin/env bash
set -euo pipefail

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Required command is not available: $cmd" >&2
    exit 1
  fi
}

require_env() {
  local var_name="$1"
  if [ -z "${!var_name:-}" ]; then
    echo "Required environment variable is empty: $var_name" >&2
    exit 1
  fi
}

require_command curl
require_command jq
require_command python3

required_vars=(
  PORTAINER_API_KEY
  TG_TOKEN
  API_KEY
  WIALON_TOKEN
  DOCKER_IMAGE
)

for var_name in "${required_vars[@]}"; do
  require_env "$var_name"
done

if [ -z "${PORTAINER_URL:-}" ]; then
  echo "PORTAINER_URL must be provided via environment variables." >&2
  exit 1
fi

PORTAINER_URL="${PORTAINER_URL%/}"
PORTAINER_STACK_ID="${PORTAINER_STACK_ID:-17}"
ENDPOINT_ID="${ENDPOINT_ID:-${PORTAINER_ENDPOINT_ID:-}}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_TEMPLATE_PATH="${STACK_TEMPLATE_PATH:-$SCRIPT_DIR/stack-compose.tpl.yml}"

if [ ! -f "$STACK_TEMPLATE_PATH" ]; then
  echo "Compose template not found: $STACK_TEMPLATE_PATH" >&2
  exit 1
fi

STACK_JSON="$(curl -fsS -H "X-API-Key: ${PORTAINER_API_KEY}" "${PORTAINER_URL}/api/stacks/${PORTAINER_STACK_ID}")"
STACK_NAME="$(echo "$STACK_JSON" | jq -r '.Name // empty')"

if [ -z "$STACK_NAME" ]; then
  echo "Unable to resolve stack name for stack id ${PORTAINER_STACK_ID}" >&2
  exit 1
fi

if [ -z "$ENDPOINT_ID" ]; then
  ENDPOINT_ID="$(echo "$STACK_JSON" | jq -r '.EndpointId // empty')"
fi

if [ -z "$ENDPOINT_ID" ]; then
  echo "ENDPOINT_ID is empty and EndpointId was not found in stack details." >&2
  exit 1
fi

export DOCKER_IMAGE TG_TOKEN API_KEY WIALON_TOKEN
STACK_FILE_CONTENT="$(
  python3 - "$STACK_TEMPLATE_PATH" <<'PY'
import os
import re
import sys

template_path = sys.argv[1]
template = open(template_path, "r", encoding="utf-8").read()

def repl(match: re.Match[str]) -> str:
    key = match.group(1)
    return os.environ.get(key, "")

rendered = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", repl, template)
sys.stdout.write(rendered)
PY
)"

CURRENT_ENV="$(echo "$STACK_JSON" | jq '.Env // []')"
UPDATED_ENV="$(
  echo "$CURRENT_ENV" | jq \
    --arg docker_image "$DOCKER_IMAGE" \
    --arg tg_token "$TG_TOKEN" \
    --arg api_key "$API_KEY" \
    --arg wialon_token "$WIALON_TOKEN" '
    def upsert($k; $v):
      if any(.[]?; .name == $k) then
        map(if .name == $k then .value = $v else . end)
      else
        . + [{"name": $k, "value": $v}]
      end;
    (. // [])
    | upsert("DOCKER_IMAGE"; $docker_image)
    | upsert("TG_TOKEN"; $tg_token)
    | upsert("API_KEY"; $api_key)
    | upsert("WIALON_TOKEN"; $wialon_token)
  '
)"

PAYLOAD="$(
  jq -n \
    --arg name "$STACK_NAME" \
    --arg compose "$STACK_FILE_CONTENT" \
    --argjson env "$UPDATED_ENV" \
    '{Name: $name, StackFileContent: $compose, Env: $env, Prune: true, PullImage: true}'
)"

curl -fsS -X PUT "${PORTAINER_URL}/api/stacks/${PORTAINER_STACK_ID}?endpointId=${ENDPOINT_ID}" \
  -H "X-API-Key: ${PORTAINER_API_KEY}" \
  -H "Content-Type: application/json" \
  --data "$PAYLOAD" >/dev/null

echo "Portainer stack ${PORTAINER_STACK_ID} updated with ${DOCKER_IMAGE}"
