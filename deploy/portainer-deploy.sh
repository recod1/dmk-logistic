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

require_env PORTAINER_URL
require_env PORTAINER_API_TOKEN
require_env PORTAINER_STACK_ID
require_env IMAGE_NAME
require_env TAG
require_env TG_TOKEN
require_env API_KEY
require_env WIALON_TOKEN

PORTAINER_URL="${PORTAINER_URL%/}"
TOKEN="$PORTAINER_API_TOKEN"
STACK_ID="$PORTAINER_STACK_ID"
ENDPOINT_ID="${PORTAINER_ENDPOINT_ID:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE_PATH="${COMPOSE_FILE_PATH:-$SCRIPT_DIR/docker-compose.test.yml}"

if [ ! -f "$COMPOSE_FILE_PATH" ]; then
  echo "Compose file not found: $COMPOSE_FILE_PATH" >&2
  exit 1
fi

STACK_JSON="$(curl -fsS -H "X-API-Key: ${TOKEN}" "${PORTAINER_URL}/api/stacks/${STACK_ID}")"
STACK_NAME="$(echo "$STACK_JSON" | jq -r '.Name // empty')"

if [ -z "$STACK_NAME" ]; then
  echo "Unable to resolve stack name for stack id ${STACK_ID}" >&2
  exit 1
fi

if [ -z "$ENDPOINT_ID" ]; then
  ENDPOINT_ID="$(echo "$STACK_JSON" | jq -r '.EndpointId // empty')"
fi

if [ -z "$ENDPOINT_ID" ]; then
  echo "PORTAINER_ENDPOINT_ID is empty and EndpointId was not found in stack details." >&2
  exit 1
fi

CURRENT_ENV="$(echo "$STACK_JSON" | jq '.Env // []')"
UPDATED_ENV="$(echo "$CURRENT_ENV" | jq \
  --arg image_name "$IMAGE_NAME" \
  --arg tag "$TAG" \
  --arg tg_token "$TG_TOKEN" \
  --arg api_key "$API_KEY" \
  --arg wialon_token "$WIALON_TOKEN" \
  --arg wialon_base_url "${WIALON_BASE_URL:-}" \
  --arg db_path "${DB_PATH:-}" \
  --arg api_port "${API_PORT:-}" '
  def upsert($k; $v):
    if ($v | length) == 0 then
      .
    elif any(.[]?; .name == $k) then
      map(if .name == $k then .value = $v else . end)
    else
      . + [{"name": $k, "value": $v}]
    end;
  (. // [])
  | upsert("IMAGE_NAME"; $image_name)
  | upsert("TAG"; $tag)
  | upsert("TG_TOKEN"; $tg_token)
  | upsert("API_KEY"; $api_key)
  | upsert("WIALON_TOKEN"; $wialon_token)
  | upsert("WIALON_BASE_URL"; $wialon_base_url)
  | upsert("DB_PATH"; $db_path)
  | upsert("API_PORT"; $api_port)
')"

PAYLOAD="$(jq -n \
  --arg name "$STACK_NAME" \
  --argjson env "$UPDATED_ENV" \
  --rawfile compose "$COMPOSE_FILE_PATH" \
  '{Name: $name, StackFileContent: $compose, Env: $env, Prune: true, PullImage: true}')"

curl -fsS -X PUT "${PORTAINER_URL}/api/stacks/${STACK_ID}?endpointId=${ENDPOINT_ID}" \
  -H "X-API-Key: ${TOKEN}" \
  -H "Content-Type: application/json" \
  --data "$PAYLOAD" >/dev/null

echo "Portainer stack ${STACK_ID} updated: ${IMAGE_NAME}:${TAG}"
