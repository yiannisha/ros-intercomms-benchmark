#!/usr/bin/env bash
set -euo pipefail

MODE="${MODE:-ping}"
ROLE="${ROLE:-server}"
OUTPUT_DIR="${OUTPUT_DIR:-results}"
DISCOVERY_TIMEOUT="${DISCOVERY_TIMEOUT:-30}"

cat >&2 <<'EOF'
Cross-network mode expects routed reachability and explicit DDS discovery when
multicast is unavailable. Configure your RMW before running, for example:
  export ROS_DISCOVERY_SERVER=<server-ip>:11811
  export FASTDDS_DEFAULT_PROFILES_FILE=/path/to/fastdds.xml
  export CYCLONEDDS_URI=file:///path/to/cyclonedds.xml
VPN/routed addresses are fine; this script does not assume a specific VPN.
EOF

exec ros2 run ros2_netbench run_benchmark \
  --mode "${MODE}" \
  --role "${ROLE}" \
  --output-dir "${OUTPUT_DIR}" \
  --discovery-timeout "${DISCOVERY_TIMEOUT}" \
  "$@"
