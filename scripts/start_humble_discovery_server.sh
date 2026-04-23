#!/usr/bin/env bash
set -euo pipefail

ROS_DISTRO="${ROS_DISTRO:-humble}"
ROS_SETUP="/opt/ros/${ROS_DISTRO}/setup.bash"
SERVER_ID="${SERVER_ID:-0}"
LISTEN_ADDRESS="${LISTEN_ADDRESS:-0.0.0.0}"
PORT="${PORT:-11811}"

if [[ ! -f "${ROS_SETUP}" ]]; then
  echo "Missing ${ROS_SETUP}; install ROS 2 ${ROS_DISTRO} before starting discovery." >&2
  exit 1
fi

set +u
source "${ROS_SETUP}"
set -u

unset ROS_DISCOVERY_SERVER DISCOVERY_SERVER

echo "[ros2_netbench] Fast DDS discovery server listening on ${LISTEN_ADDRESS}:${PORT} with id ${SERVER_ID}" >&2
exec fastdds discovery -i "${SERVER_ID}" -l "${LISTEN_ADDRESS}" -p "${PORT}"
