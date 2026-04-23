#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -n "${DISCOVERY_SERVER:-}" && -z "${ROS_DISCOVERY_SERVER:-}" ]]; then
  export ROS_DISCOVERY_SERVER="${DISCOVERY_SERVER}"
fi

if [[ -n "${CYCLONEDDS_CONFIG:-}" && -z "${CYCLONEDDS_URI:-}" ]]; then
  export CYCLONEDDS_URI="file://${CYCLONEDDS_CONFIG}"
fi

source "${SCRIPT_DIR}/_humble_env.sh"

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
[ros2_netbench] cross-network stream/${ROLE}
  ROS_DOMAIN_ID=${ROS_DOMAIN_ID}
  RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-ros-default}
  ROS_DISCOVERY_SERVER=${ROS_DISCOVERY_SERVER:-not-set}
  CYCLONEDDS_URI=${CYCLONEDDS_URI:-not-set}

This is still normal ROS 2 pub/sub over DDS. Across routed networks or
tailnets, default multicast discovery often does not cross the network
boundary, so configure your selected RMW explicitly before starting both roles.
EOF

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

exec ros2 run ros2_netbench run_benchmark "${ARGS[@]}" "$@"
