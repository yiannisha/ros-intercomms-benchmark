#!/usr/bin/env bash
set -euo pipefail

IMAGE="${IMAGE:-ros2-netbench:jazzy}"
CONTAINER_NAME="${CONTAINER_NAME:-ros2-netbench-dev-$$}"
ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"

docker build -f Dockerfile.ros2 -t "${IMAGE}" .

docker run --rm -it \
  --name "${CONTAINER_NAME}" \
  --volume "${PWD}:/workspace" \
  --workdir /workspace \
  --env "ROS_DOMAIN_ID=${ROS_DOMAIN_ID}" \
  --env "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION}" \
  "${IMAGE}" \
  bash -lc '
    set -eo pipefail
    source /opt/ros/jazzy/setup.bash
    if [[ ! -f install/setup.bash ]]; then
      colcon build --symlink-install
    fi
    source install/setup.bash
    exec bash
  '
