#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_humble_env.sh"

ROLE="${ROLE:-receiver}"
OUTPUT_DIR="${OUTPUT_DIR:-results}"
PAYLOAD_SIZE="${PAYLOAD_SIZE:-1024}"
RATE_HZ="${RATE_HZ:-10}"
DURATION="${DURATION:-10}"
WARMUP="${WARMUP:-2}"
RELIABILITY="${RELIABILITY:-reliable}"
DEPTH="${DEPTH:-10}"
TOPIC="${TOPIC:-/netbench/stream}"
DISCOVERY_TIMEOUT="${DISCOVERY_TIMEOUT:-10}"

ARGS=(
  --mode stream
  --role "${ROLE}"
  --topic "${TOPIC}"
  --payload-size "${PAYLOAD_SIZE}"
  --rate-hz "${RATE_HZ}"
  --duration "${DURATION}"
  --warmup "${WARMUP}"
  --output-dir "${OUTPUT_DIR}"
  --reliability "${RELIABILITY}"
  --depth "${DEPTH}"
  --discovery-timeout "${DISCOVERY_TIMEOUT}"
)

if [[ -n "${SESSION_ID:-}" ]]; then
  ARGS+=(--session-id "${SESSION_ID}")
fi

echo "[ros2_netbench] same-LAN stream/${ROLE}: domain=${ROS_DOMAIN_ID} rmw=${RMW_IMPLEMENTATION:-ros-default}" >&2
exec ros2 run ros2_netbench run_benchmark "${ARGS[@]}" "$@"
