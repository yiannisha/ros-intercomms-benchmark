#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/_humble_env.sh"

OUTPUT_DIR="${OUTPUT_DIR:-results/local_stream}"
PAYLOAD_SIZE="${PAYLOAD_SIZE:-1024}"
RATE_HZ="${RATE_HZ:-100}"
DURATION="${DURATION:-10}"
WARMUP="${WARMUP:-2}"
RELIABILITY="${RELIABILITY:-reliable}"
DEPTH="${DEPTH:-10}"
TOPIC="${TOPIC:-/netbench/stream}"
DISCOVERY_TIMEOUT="${DISCOVERY_TIMEOUT:-10}"
RECEIVER_START_DELAY="${RECEIVER_START_DELAY:-1}"
SESSION_ID="${SESSION_ID:-$(( ( $(date +%s) << 16 ) + ( $$ & 65535 ) ))}"
RECEIVER_RUN_ID="${RECEIVER_RUN_ID:-local_receiver_${SESSION_ID}}"
SENDER_RUN_ID="${SENDER_RUN_ID:-local_sender_${SESSION_ID}}"

COMMON_ARGS=(
  --mode stream
  --topic "${TOPIC}"
  --payload-size "${PAYLOAD_SIZE}"
  --rate-hz "${RATE_HZ}"
  --duration "${DURATION}"
  --warmup "${WARMUP}"
  --output-dir "${OUTPUT_DIR}"
  --reliability "${RELIABILITY}"
  --depth "${DEPTH}"
  --discovery-timeout "${DISCOVERY_TIMEOUT}"
  --session-id "${SESSION_ID}"
)

RECEIVER_PID=""
cleanup() {
  if [[ -n "${RECEIVER_PID}" ]] && kill -0 "${RECEIVER_PID}" 2>/dev/null; then
    kill "${RECEIVER_PID}" 2>/dev/null || true
    wait "${RECEIVER_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "[ros2_netbench] local stream receiver starting: domain=${ROS_DOMAIN_ID} rmw=${RMW_IMPLEMENTATION:-ros-default} session=${SESSION_ID}" >&2
ros2 run ros2_netbench run_benchmark \
  "${COMMON_ARGS[@]}" \
  --role receiver \
  --run-id "${RECEIVER_RUN_ID}" \
  "$@" &
RECEIVER_PID="$!"

sleep "${RECEIVER_START_DELAY}"

echo "[ros2_netbench] local stream sender starting: domain=${ROS_DOMAIN_ID} rmw=${RMW_IMPLEMENTATION:-ros-default} session=${SESSION_ID}" >&2
ros2 run ros2_netbench run_benchmark \
  "${COMMON_ARGS[@]}" \
  --role sender \
  --run-id "${SENDER_RUN_ID}" \
  "$@"

wait "${RECEIVER_PID}"
RECEIVER_PID=""

echo "[ros2_netbench] local stream results: ${OUTPUT_DIR}/${RECEIVER_RUN_ID} and ${OUTPUT_DIR}/${SENDER_RUN_ID}" >&2
