#!/usr/bin/env bash
set -euo pipefail

require_var() {
  local var_name="$1"
  if [ -z "${!var_name:-}" ]; then
    echo "Missing required env var: ${var_name}" >&2
    exit 1
  fi
}

require_var PORTAINER_URL
require_var PORTAINER_API_TOKEN
require_var PORTAINER_STACK_ID
require_var IMAGE_NAME
require_var TAG
require_var TG_TOKEN
require_var API_KEY
require_var WIALON_TOKEN

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-${SCRIPT_DIR}/docker-compose.test.yml}"
PORTAINER_URL="${PORTAINER_URL%/}"
STACK_ID="${PORTAINER_STACK_ID}"

if [ ! -f "${COMPOSE_FILE}" ]; then
  echo "Compose file not found: ${COMPOSE_FILE}" >&2
  exit 1
fi

for cmd in curl jq; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Required command not found: ${cmd}" >&2
    exit 1
  fi
done

STACK_JSON="$(curl -fsS \
  -H "X-API-Key: ${PORTAINER_API_TOKEN}" \
  "${PORTAINER_URL}/api/stacks/${STACK_ID}")"

STACK_NAME="$(echo "${STACK_JSON}" | jq -r '.Name // .name // empty')"
if [ -z "${STACK_NAME}" ]; then
  echo "Unable to determine stack name for stack id ${STACK_ID}" >&2
  exit 1
fi

ENDPOINT_ID="${PORTAINER_ENDPOINT_ID:-}"
if [ -z "${ENDPOINT_ID}" ]; then
  ENDPOINT_ID="$(echo "${STACK_JSON}" | jq -r '.EndpointId // .endpointId // empty')"
fi
if [ -z "${ENDPOINT_ID}" ]; then
  echo "PORTAINER_ENDPOINT_ID is not set and EndpointId not found in stack metadata." >&2
  exit 1
fi

# Best-effort read to verify stack file endpoint (some versions require endpointId query).
if ! curl -fsS \
  -H "X-API-Key: ${PORTAINER_API_TOKEN}" \
  "${PORTAINER_URL}/api/stacks/${STACK_ID}/file" >/dev/null 2>&1; then
  curl -fsS \
    -H "X-API-Key: ${PORTAINER_API_TOKEN}" \
    "${PORTAINER_URL}/api/stacks/${STACK_ID}/file?endpointId=${ENDPOINT_ID}" >/dev/null 2>&1 || true
fi

CURRENT_ENV="$(echo "${STACK_JSON}" | jq '
  (.Env // .env // [])
  | map(
      if (has("name") and has("value")) then
        {name: (.name | tostring), value: (.value | tostring)}
      elif (has("Name") and has("Value")) then
        {name: (.Name | tostring), value: (.Value | tostring)}
      else
        empty
      end
    )
')"

UPDATED_ENV="$(echo "${CURRENT_ENV}" | jq \
  --arg image_name "${IMAGE_NAME}" \
  --arg tag "${TAG}" \
  --arg tg_token "${TG_TOKEN}" \
  --arg api_key "${API_KEY}" \
  --arg wialon_token "${WIALON_TOKEN}" \
  --arg wialon_base_url "${WIALON_BASE_URL:-}" \
  --arg db_path "${DB_PATH:-}" \
  --arg api_port "${API_PORT:-}" \
  --arg deploy_path "${DEPLOY_PATH:-}" '
  def upsert($k; $v):
    if ($v | length) == 0 then
      .
    elif any(.[]?; .name == $k) then
      map(if .name == $k then .value = $v else . end)
    else
      . + [{name: $k, value: $v}]
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
  | upsert("DEPLOY_PATH"; $deploy_path)
')"

LOWER_PAYLOAD_FILE="$(mktemp)"
UPPER_PAYLOAD_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "${LOWER_PAYLOAD_FILE}" "${UPPER_PAYLOAD_FILE}" "${RESPONSE_FILE}"' EXIT

jq -n \
  --arg stack_name "${STACK_NAME}" \
  --argjson env "${UPDATED_ENV}" \
  --rawfile compose "${COMPOSE_FILE}" \
  '{
    name: $stack_name,
    stackFileContent: $compose,
    env: $env,
    prune: true,
    pullImage: true
  }' > "${LOWER_PAYLOAD_FILE}"

jq -n \
  --arg stack_name "${STACK_NAME}" \
  --argjson env "${UPDATED_ENV}" \
  --rawfile compose "${COMPOSE_FILE}" \
  '{
    Name: $stack_name,
    StackFileContent: $compose,
    Env: $env,
    Prune: true,
    PullImage: true
  }' > "${UPPER_PAYLOAD_FILE}"

try_update() {
  local payload_file="$1"
  local status

  status="$(curl -sS -o "${RESPONSE_FILE}" -w "%{http_code}" \
    -X PUT "${PORTAINER_URL}/api/stacks/${STACK_ID}?endpointId=${ENDPOINT_ID}" \
    -H "X-API-Key: ${PORTAINER_API_TOKEN}" \
    -H "Content-Type: application/json" \
    --data "@${payload_file}")"

  if [ "${status}" -ge 200 ] && [ "${status}" -lt 300 ]; then
    return 0
  fi

  echo "Portainer update failed with HTTP ${status}" >&2
  cat "${RESPONSE_FILE}" >&2 || true
  return 1
}

if ! try_update "${LOWER_PAYLOAD_FILE}"; then
  echo "Retrying stack update with legacy payload keys..." >&2
  try_update "${UPPER_PAYLOAD_FILE}"
fi

echo "Stack ${STACK_ID} updated in Portainer endpoint ${ENDPOINT_ID} with ${IMAGE_NAME}:${TAG}"
