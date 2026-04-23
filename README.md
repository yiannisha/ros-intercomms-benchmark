# ros2_netbench

`ros2_netbench` is a small ROS 2 pub/sub stream benchmark. It exists to answer one question:

> If one ROS 2 node publishes a stream on one machine, how well does another ROS 2 node receive it on another machine?

The benchmark uses normal ROS 2 communication through `rclpy`, the active RMW implementation, DDS discovery, DDS QoS, and a custom ROS 2 message. It does not replace ROS 2 networking with a custom socket protocol.

## What Is Included

- One publisher role: sends `BenchmarkPacket` messages at a configured rate.
- One subscriber role: receives the stream and writes delivery metrics.
- One custom message package: `ros2_netbench_interfaces/msg/BenchmarkPacket.msg`.
- Result artifacts: `run_metadata.json`, `summary.json`, and `raw_samples.csv`.
- Optional local process/NIC sampling with `--sample-system --nic <interface>`.
- Optional `rosbag2` recording with `--bag`.

The repo intentionally does not include service benchmarks, ping/pong RTT benchmarks, alternate transports, or application-specific discovery code.

## Important ROS 2 Networking Reality

ROS 2 uses DDS by default. On a simple same-LAN setup, DDS discovery is usually automatic when both machines use the same `ROS_DOMAIN_ID` and compatible RMW/QoS settings.

Across routed networks, VPNs, or tailnets, multicast discovery often does not cross the network boundary. That is still a ROS 2/DDS problem, not something this benchmark hides. Configure the RMW explicitly before running the benchmark:

- Fast DDS: run a Fast DDS discovery server and set `ROS_DISCOVERY_SERVER=<server-ip>:11811` on both machines.
- Cyclone DDS: install `rmw_cyclonedds_cpp`, set `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`, and set `CYCLONEDDS_URI=file:///path/to/cyclonedds-peers.xml` with explicit peer addresses.

For ROS 2 Humble, ROS 2 documentation says DDS is the default middleware and Fast DDS is the default RMW vendor. The benchmark does not force that default; it uses whichever RMW your ROS 2 environment selects.

References:

- ROS 2 Humble RMW implementations: https://docs.ros.org/en/humble/Installation/RMW-Implementations.html
- ROS 2 discovery concept: https://docs.ros.org/en/humble/Concepts/Basic/About-Discovery.html
- ROS 2 Fast DDS discovery server tutorial: https://docs.ros.org/en/humble/Tutorials/Advanced/Discovery-Server/Discovery-Server.html
- Cyclone DDS configuration guide: https://cyclonedds.io/docs/cyclonedds/latest/config/index

## Build

Install ROS 2 and `colcon`, then build from the repo root:

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

The helper script defaults to Humble but also respects `ROS_DISTRO`:

```bash
scripts/setup_humble_workspace.sh
```

## Local Loopback Smoke Test

Run both roles on one machine:

```bash
DURATION=10 RATE_HZ=100 PAYLOAD_SIZE=1024 scripts/run_local_stream.sh
```

The subscriber summary is the main artifact:

```bash
ros2 run ros2_netbench summarize_run results/local_stream/local_receiver_<session-id>
```

## Same-LAN Test

Use the same `ROS_DOMAIN_ID` on both machines. Start the subscriber first.

Machine B:

```bash
ROS_DOMAIN_ID=42 ROLE=receiver OUTPUT_DIR=results/lan_rx \
  DURATION=30 RATE_HZ=100 PAYLOAD_SIZE=1024 \
  scripts/run_same_lan.sh
```

Machine A:

```bash
ROS_DOMAIN_ID=42 ROLE=sender OUTPUT_DIR=results/lan_tx \
  DURATION=30 RATE_HZ=100 PAYLOAD_SIZE=1024 \
  scripts/run_same_lan.sh
```

If same-LAN discovery does not work, first verify normal ROS 2 discovery with `ros2 node list` or a standard talker/listener demo in the same environment. This benchmark should not be your first discovery diagnostic tool.

## Cross-Network With Fast DDS Discovery Server

Run this on a machine both devices can reach:

```bash
LISTEN_ADDRESS=0.0.0.0 PORT=11811 scripts/start_humble_discovery_server.sh
```

On both benchmark machines, set the same domain and discovery server. Start the subscriber first.

Machine B:

```bash
ROS_DOMAIN_ID=42 \
RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
ROS_DISCOVERY_SERVER=<server-ip>:11811 \
SESSION_ID=4242 \
ROLE=receiver \
OUTPUT_DIR=results/cross_rx \
DISCOVERY_TIMEOUT=30 \
scripts/run_cross_network.sh
```

Machine A:

```bash
ROS_DOMAIN_ID=42 \
RMW_IMPLEMENTATION=rmw_fastrtps_cpp \
ROS_DISCOVERY_SERVER=<server-ip>:11811 \
SESSION_ID=4242 \
ROLE=sender \
OUTPUT_DIR=results/cross_tx \
DURATION=30 RATE_HZ=100 PAYLOAD_SIZE=1024 \
DISCOVERY_TIMEOUT=30 \
scripts/run_cross_network.sh
```

`DISCOVERY_SERVER=<server-ip>:11811` is accepted as a shorthand for `ROS_DISCOVERY_SERVER`.

## Cross-Network With Cyclone DDS Static Peers

Install Cyclone DDS RMW on both machines if it is not already available:

```bash
sudo apt install ros-${ROS_DISTRO:-humble}-rmw-cyclonedds-cpp
```

Create a Cyclone DDS peer config on each machine. Use each machine's own tailnet/VPN address as `INTERFACE_ADDRESS` and the other machine's address as `PEERS`.

Machine B:

```bash
PEERS=<machine-a-ip> INTERFACE_ADDRESS=<machine-b-ip> \
  OUTPUT=cyclonedds-peers.xml scripts/write_cyclonedds_peers.sh
```

Machine A:

```bash
PEERS=<machine-b-ip> INTERFACE_ADDRESS=<machine-a-ip> \
  OUTPUT=cyclonedds-peers.xml scripts/write_cyclonedds_peers.sh
```

Then run the benchmark with Cyclone DDS on both machines:

```bash
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file://$PWD/cyclonedds-peers.xml
```

Machine B:

```bash
SESSION_ID=4242 ROLE=receiver OUTPUT_DIR=results/cyclone_rx \
  DISCOVERY_TIMEOUT=30 scripts/run_cross_network.sh
```

Machine A:

```bash
SESSION_ID=4242 ROLE=sender OUTPUT_DIR=results/cyclone_tx \
  DURATION=30 RATE_HZ=100 PAYLOAD_SIZE=1024 \
  DISCOVERY_TIMEOUT=30 scripts/run_cross_network.sh
```

## Direct CLI

Subscriber:

```bash
ros2 run ros2_netbench run_benchmark \
  --role receiver \
  --topic /netbench/stream \
  --duration 30 --warmup 3 \
  --output-dir results
```

Publisher:

```bash
ros2 run ros2_netbench run_benchmark \
  --role sender \
  --topic /netbench/stream \
  --rate-hz 100 --payload-size 1024 \
  --duration 30 --warmup 3 \
  --output-dir results
```

Common options:

```bash
--session-id 4242
--reliability reliable|best_effort
--depth 10
--sample-system --nic tailscale0
--clock-sync ok
--clock-sync offset --clock-offset-ms 0.42
```

One-way latency is marked invalid unless you explicitly confirm clock synchronization with `--clock-sync ok` or provide an offset. Throughput, loss, duplicates, out-of-order delivery, and jitter do not require synchronized wall clocks.

## Output

Each role writes a run directory under `--output-dir`:

```text
results/<run_id>/
  run_metadata.json
  summary.json
  raw_samples.csv
  system_stats.csv        # only with --sample-system
  rosbag/                 # only with --bag
```

`summary.json` includes:

- sent and received message counts
- application-level sequence loss
- duplicate and out-of-order counts
- throughput in messages/sec and payload bytes/sec
- inter-arrival jitter
- publish-period jitter
- optional one-way latency
- discovery and first-packet timing
- optional process/NIC samples

Post-run helpers:

```bash
ros2 run ros2_netbench summarize_run results/<run_id>
ros2 run ros2_netbench compare_runs results/run_a results/run_b --output comparison.md
```

## Troubleshooting

1. Confirm both machines built and sourced the same workspace.
2. Confirm `ROS_DOMAIN_ID` matches.
3. Confirm `RMW_IMPLEMENTATION` matches your intended middleware.
4. Confirm `ROS_LOCALHOST_ONLY` is not set to `1`.
5. On same LAN, verify multicast is allowed by the network and host firewall.
6. Across a tailnet/VPN, use Fast DDS discovery server or Cyclone DDS static peers instead of assuming multicast discovery will work.
7. Keep topic name and QoS compatible on both roles.
8. Increase `DISCOVERY_TIMEOUT` for slow cross-network discovery.

## Tests

Run pure unit tests:

```bash
python3 -m pytest tests/unit
```

Run the loopback integration test from a sourced ROS 2 workspace:

```bash
source install/setup.bash
python3 -m pytest tests/integration
```

The integration test skips automatically if `rclpy` or the generated interface package is unavailable.
