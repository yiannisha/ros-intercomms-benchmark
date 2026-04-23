#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -n "${DISCOVERY_SERVER:-}" && -z "${ROS_DISCOVERY_SERVER:-}" ]]; then
  export ROS_DISCOVERY_SERVER="${DISCOVERY_SERVER}"
fi

source "${SCRIPT_DIR}/_humble_env.sh"

MODE="${MODE:-stream}"
ROLE="${ROLE:-receiver}"
OUTPUT_DIR="${OUTPUT_DIR:-results}"
PAYLOAD_SIZE="${PAYLOAD_SIZE:-1024}"
RATE_HZ="${RATE_HZ:-10}"
DURATION="${DURATION:-30}"
WARMUP="${WARMUP:-3}"
RELIABILITY="${RELIABILITY:-reliable}"
DEPTH="${DEPTH:-10}"
TOPIC="${TOPIC:-/netbench/stream}"
DISCOVERY_TIMEOUT="${DISCOVERY_TIMEOUT:-30}"

cat >&2 <<EOF
Cross-network mode expects routed reachability and explicit DDS discovery when
multicast is unavailable. Configure your RMW before running, for example:
  export ROS_DISCOVERY_SERVER=<server-ip>:11811
  # or use the shorthand accepted by this script:
  export DISCOVERY_SERVER=<server-ip>:11811
  export FASTDDS_DEFAULT_PROFILES_FILE=/path/to/fastdds.xml
  export CYCLONEDDS_URI=file:///path/to/cyclonedds.xml
VPN/routed addresses are fine; this script does not assume a specific VPN.
EOF

ARGS=(
  --mode "${MODE}"
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

echo "[ros2_netbench] cross-network ${MODE}/${ROLE}: domain=${ROS_DOMAIN_ID} rmw=${RMW_IMPLEMENTATION} discovery=${ROS_DISCOVERY_SERVER:-not-set}" >&2
exec ros2 run ros2_netbench run_benchmark "${ARGS[@]}" "$@"
