#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROS_DISTRO="${ROS_DISTRO:-humble}"
ROS_SETUP="/opt/ros/${ROS_DISTRO}/setup.bash"

if [[ "${ROS_DISTRO}" != "humble" ]]; then
  echo "This runner is pinned to ROS 2 Humble. Set ROS_DISTRO=humble." >&2
  return 2 2>/dev/null || exit 2
fi

if [[ ! -f "${ROS_SETUP}" ]]; then
  echo "Missing ${ROS_SETUP}; install ROS 2 Humble before running the benchmark." >&2
  return 1 2>/dev/null || exit 1
fi

set +u
source "${ROS_SETUP}"
set -u

export ROS_DISTRO="humble"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"

if [[ "${ROS2_NETBENCH_AUTO_BUILD:-1}" == "1" && ! -f "${REPO_ROOT}/install/setup.bash" ]]; then
  "${SCRIPT_DIR}/setup_humble_workspace.sh"
fi

if [[ ! -f "${REPO_ROOT}/install/setup.bash" ]]; then
  echo "Missing ${REPO_ROOT}/install/setup.bash; run scripts/setup_humble_workspace.sh first." >&2
  return 1 2>/dev/null || exit 1
fi

set +u
source "${REPO_ROOT}/install/setup.bash"
set -u
