#!/usr/bin/bash

export PEERS=100.92.111.95
export INTERFACE_ADDRESS=100.118.2.108
export OUTPUT=cyclonedds-peers.xml

export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file://$PWD/cyclonedds-peers.xml
export ROS_LOCALHOST_ONLY=0

export SESSION_ID=4242
export ROLE=receiver
export OUTPUT_DIR=results/cross_rx
export DISCOVERY_TIMEOUT=30
export DURATION=30
export WARMUP=3
export RATE_HZ=100
export PAYLOAD_SIZE=1024

