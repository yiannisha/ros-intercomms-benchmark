#!/usr/bin/env bash
set -euo pipefail

ROS_DISTRO="${ROS_DISTRO:-humble}"
IMAGE="${IMAGE:-ros2-netbench:${ROS_DISTRO}}"
CONTAINER_NAME="${CONTAINER_NAME:-ros2-netbench-dev-$$}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
RMW_ENV=()
if [[ -n "${RMW_IMPLEMENTATION:-}" ]]; then
  RMW_ENV+=(--env "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION}")
fi

docker build --build-arg "ROS_DISTRO=${ROS_DISTRO}" -f Dockerfile.ros2 -t "${IMAGE}" .

docker run --rm -it \
  --name "${CONTAINER_NAME}" \
  --volume "${PWD}:/workspace" \
  --workdir /workspace \
  --env "ROS_DOMAIN_ID=${ROS_DOMAIN_ID}" \
  --env "ROS_DISTRO=${ROS_DISTRO}" \
  "${RMW_ENV[@]}" \
  "${IMAGE}" \
  bash -lc '
    set -eo pipefail
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
    if [[ ! -f install/setup.bash ]]; then
      colcon build --symlink-install
    fi
    source install/setup.bash
    exec bash
  '
