#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROS_DISTRO="${ROS_DISTRO:-humble}"
ROS_SETUP="/opt/ros/${ROS_DISTRO}/setup.bash"

if [[ ! -f "${ROS_SETUP}" ]]; then
  cat >&2 <<EOF
Missing ${ROS_SETUP}.
Install ROS 2 ${ROS_DISTRO} first, then rerun:
  sudo apt install ros-${ROS_DISTRO}-ros-base python3-colcon-common-extensions
EOF
  exit 1
fi

set +u
source "${ROS_SETUP}"
set -u

if ! command -v colcon >/dev/null 2>&1; then
  echo "Missing colcon. Install python3-colcon-common-extensions and rerun." >&2
  exit 1
fi

cd "${REPO_ROOT}"
colcon build --symlink-install "$@"
