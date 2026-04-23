#!/usr/bin/env bash
set -euo pipefail

ROS_DISTRO="${ROS_DISTRO:-humble}"
IMAGE="${IMAGE:-ros2-netbench-test:${ROS_DISTRO}}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"

docker build --build-arg "ROS_DISTRO=${ROS_DISTRO}" -f Dockerfile.ros2 -t "${IMAGE}" .

docker run --rm \
  --volume "${PWD}:/workspace" \
  --workdir /workspace \
  --env "ROS_DOMAIN_ID=${ROS_DOMAIN_ID}" \
  --env "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION}" \
  --env "ROS_DISTRO=${ROS_DISTRO}" \
  "${IMAGE}" \
  bash -lc '
    set -eo pipefail
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
    set -uo pipefail
    rm -rf build install log
    colcon build --symlink-install
    set +u
    source install/setup.bash
    set -u
    python3 -m pytest tests/unit
    python3 -m pytest tests/integration
  '
