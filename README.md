# ros2_netbench

`ros2_netbench` is a Python ROS 2 benchmarking toolkit for measuring application-level communication quality between two machines. It is Linux-first, uses `rclpy`, supports ROS 2 Humble and Jazzy or newer, and writes machine-readable artifacts for repeatable experiments.

The repo contains two ROS 2 packages:

- `ros2_netbench_interfaces`: custom packet message and echo service definitions.
- `ros2_netbench`: Python benchmark nodes, CLI runner, launch files, analysis helpers, and Linux scripts.

## What It Measures

The toolkit measures ROS 2 application-level behavior:

- Pub/sub stream delivery quality: throughput, loss inferred from sequence gaps, duplicates, out-of-order delivery, inter-arrival jitter, publish-period jitter, and optional one-way latency.
- Ping/pong RTT: round-trip latency without synchronized clocks.
- Service latency: request/response latency, timeout rate, achieved request rate.
- Session timing: discovery time, connection-ready time, experiment start/end timestamps.
- Optional local process and NIC sampling: CPU percent, RSS memory, NIC TX/RX bps when a Linux interface is provided.

It does not measure raw IP packet loss directly. Application-level message loss is the number of missing ROS benchmark sequence numbers observed by the receiver/client. Raw packet loss can be lower or higher depending on DDS fragmentation, retransmission, QoS reliability, kernel queues, Wi-Fi behavior, and middleware buffering.

## Build

Install ROS 2 Humble, Jazzy, or newer, source your ROS environment, then build the workspace from the repo root:

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

No non-ROS Python runtime dependencies are required for the benchmark logic.

### Docker Development Environment

On machines without a native ROS 2 install, use the repo-local Docker environment:

```bash
scripts/dev_shell.sh
```

The script builds the `ros2-netbench:humble` image by default, mounts the repo at `/workspace`, sources ROS 2, runs `colcon build --symlink-install` if the workspace has not been built yet, sources `install/setup.bash`, and opens a shell ready for `ros2 run ...` commands.

Use another supported distro by setting `ROS_DISTRO`:

```bash
ROS_DISTRO=jazzy scripts/dev_shell.sh
```

Run the repeatable Docker build and test path:

```bash
ROS_DISTRO=humble scripts/test_ros_distro.sh
ROS_DISTRO=jazzy scripts/test_ros_distro.sh
```

From inside that shell, verify the environment with:

```bash
python3 -m pytest tests/unit
python3 -m pytest tests/integration
```

Docker Desktop is useful for local development and loopback testing. For real LAN or cross-network benchmarking, a native Linux ROS 2 environment is still recommended because DDS multicast, host networking, and NIC-level impairment tools behave differently inside Docker Desktop.

## Benchmark Modes

### 1. Pub/Sub Stream

Machine B, receiver:

```bash
ros2 run ros2_netbench run_benchmark \
  --mode stream --role receiver \
  --domain-id 42 \
  --topic /netbench/stream \
  --rate-hz 100 --payload-size 1024 \
  --duration 30 --warmup 3 \
  --output-dir results
```

Machine A, sender:

```bash
ros2 run ros2_netbench run_benchmark \
  --mode stream --role sender \
  --domain-id 42 \
  --topic /netbench/stream \
  --rate-hz 100 --payload-size 1024 \
  --duration 30 --warmup 3 \
  --output-dir results
```

Start the receiver before the sender. When `--session-id` is not provided, receivers accept the first session they see; senders generate a random session ID. Provide the same `--session-id` on both sides when you want strict filtering.

For stream mode, read the receiver's `summary.json` for delivery metrics such as `received_messages`, `application_level_loss_count`, jitter, duplicates, and out-of-order counts. The sender summary reports local publish stats, so `received_messages` is intentionally `null` there.

### 2. Ping/Pong RTT

Machine B, server:

```bash
ros2 run ros2_netbench run_benchmark \
  --mode ping --role server \
  --domain-id 42 \
  --topic /netbench/ping \
  --echo-topic /netbench/pong \
  --output-dir results
```

Machine A, client:

```bash
ros2 run ros2_netbench run_benchmark \
  --mode ping --role client \
  --domain-id 42 \
  --topic /netbench/ping \
  --echo-topic /netbench/pong \
  --rate-hz 50 --payload-size 512 \
  --duration 30 --warmup 3 \
  --request-timeout 1.0 \
  --output-dir results
```

RTT uses the client's monotonic clock and does not require synchronized wall clocks.

### 3. Service Benchmark

Machine B, service server:

```bash
ros2 run ros2_netbench run_benchmark \
  --mode service --role server \
  --domain-id 42 \
  --service /netbench/service \
  --output-dir results
```

Machine A, service client:

```bash
ros2 run ros2_netbench run_benchmark \
  --mode service --role client \
  --domain-id 42 \
  --service /netbench/service \
  --rate-hz 20 --payload-size 1024 \
  --duration 30 --warmup 3 \
  --request-timeout 1.0 \
  --output-dir results
```

## Same-LAN Quick Start

On both machines, use the same ROS domain ID and source the workspace:

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
export ROS_DOMAIN_ID=42
```

Then run the receiver/server first and sender/client second. Same-subnet multicast discovery should work with the default RMW configuration if host firewalls allow DDS traffic.

You can also use launch files:

```bash
ros2 launch ros2_netbench same_lan_stream.launch.py role:=receiver duration:=30 rate_hz:=100
ros2 launch ros2_netbench same_lan_stream.launch.py role:=sender duration:=30 rate_hz:=100
```

## Cross-Network Real

1. Build On Both Devices
```bash
cd /home/eden/ros-intercomms-benchmark
scripts/setup_humble_workspace.sh
```

2. Start Discovery Server
Run this on one device that both devices can reach. Replace <server-bind-ip> with that device’s reachable interface IP, or use
`0.0.0.0.`

```bash
cd /home/eden/ros-intercomms-benchmark
LISTEN_ADDRESS=0.0.0.0 PORT=11811 scripts/start_humble_discovery_server.sh
```

Keep this terminal open.

3. Start Receiver
Run this on the receiving device first. Replace <server-ip> with the IP of the device running the discovery server.

```bash
cd /home/eden/ros-intercomms-benchmark
ROS_DOMAIN_ID=42 \
ROS_DISCOVERY_SERVER=<server-ip>:11811 \
SESSION_ID=4242 \
ROLE=receiver \
OUTPUT_DIR=results/cross_rx \
DURATION=30 \
WARMUP=3 \
RATE_HZ=100 \
PAYLOAD_SIZE=1024 \
scripts/run_cross_network.sh
```

4. Start Sender
Run this on the sending device second.

```bash
cd /home/eden/ros-intercomms-benchmark
ROS_DOMAIN_ID=42 \
ROS_DISCOVERY_SERVER=<server-ip>:11811 \
SESSION_ID=4242 \
ROLE=sender \
OUTPUT_DIR=results/cross_tx \
DURATION=30 \
WARMUP=3 \
RATE_HZ=100 \
PAYLOAD_SIZE=1024 \
scripts/run_cross_network.sh
```

## Cross-Network Quick Start

Across routed networks, VPNs, or Tailscale-style overlays, do not assume multicast discovery works. The benchmark code does not hardcode a VPN provider; it only requires IP reachability and a DDS discovery setup that can find peers.

Common options:

- Fast DDS discovery server: set `ROS_DISCOVERY_SERVER=<server-ip>:11811` on both machines, or provide a Fast DDS XML profile through `FASTDDS_DEFAULT_PROFILES_FILE`.
- Cyclone DDS static peers: set `CYCLONEDDS_URI=file:///path/to/cyclonedds.xml` with peer addresses.
- Any routed/VPN network is acceptable if DDS discovery and data paths are reachable.

Example RTT over a routed/VPN network:

Machine B:

```bash
export ROS_DOMAIN_ID=42
export ROS_DISCOVERY_SERVER=100.64.0.10:11811
ros2 run ros2_netbench run_benchmark --mode ping --role server --discovery-timeout 30
```

Machine A:

```bash
export ROS_DOMAIN_ID=42
export ROS_DISCOVERY_SERVER=100.64.0.10:11811
ros2 run ros2_netbench run_benchmark \
  --mode ping --role client \
  --rate-hz 20 --payload-size 1024 \
  --duration 60 --warmup 5 \
  --discovery-timeout 30
```

The wrapper script prints the same reminder:

```bash
MODE=ping ROLE=server scripts/run_cross_network.sh
MODE=ping ROLE=client scripts/run_cross_network.sh --duration 60
```

## QoS Examples

Reliable, deeper queue:

```bash
ros2 run ros2_netbench run_benchmark \
  --mode stream --role sender \
  --reliability reliable --history keep_last --depth 50
```

Best effort:

```bash
ros2 run ros2_netbench run_benchmark \
  --mode stream --role sender \
  --reliability best_effort --history keep_last --depth 10
```

Other QoS controls:

```bash
--durability volatile
--durability transient_local
--deadline-ms 100
--liveliness automatic
--liveliness manual_by_topic
```

Use matching QoS on both sides unless you are intentionally testing incompatibility or discovery behavior.

## Payload Size Examples

Small control-style packets:

```bash
--payload-size 64 --rate-hz 100
```

Larger payloads:

```bash
--payload-size 1048576 --rate-hz 5
```

`--payload-size` controls the allocated `uint8[] payload` length in each benchmark packet. ROS/DDS framing adds additional wire overhead.

## Clock Synchronization

The packet includes both sender monotonic and sender wall-clock timestamps:

- Monotonic timestamps are used for local intervals, publish jitter, receive jitter, RTT, and service latency.
- Wall-clock timestamps are used only for one-way latency across machines.

One-way latency is disabled by default because unsynchronized clocks produce misleading values:

```json
"one_way_latency": {
  "valid": false,
  "reason": "clock_sync_unknown"
}
```

Check clock status:

```bash
scripts/sync_clock_check.sh user@machine-b
```

Enable one-way latency only when clocks are synchronized well enough:

```bash
--clock-sync ok
```

Or provide a measured receiver-minus-sender offset:

```bash
--clock-sync offset --clock-offset-ms 0.42 --max-clock-offset-ms 1.0
```

RTT and service latency remain valid without wall-clock synchronization.

## Network Impairment

The Linux `tc netem` helper supports latency, jitter, loss, duplication, reordering, and rate limiting.

Show current qdisc:

```bash
scripts/impair_network.sh show eth0
```

Apply latency, jitter, and packet loss:

```bash
sudo scripts/impair_network.sh apply eth0 \
  --latency-ms 40 \
  --jitter-ms 5 \
  --loss-pct 1
```

Apply rate limiting:

```bash
sudo scripts/impair_network.sh apply eth0 --rate 10mbit
```

Clear impairment:

```bash
sudo scripts/impair_network.sh clear eth0
```

## Output Artifacts

Each role writes a run directory under `--output-dir`:

```text
results/<run_id>/
  run_metadata.json
  summary.json
  raw_samples.csv
  system_stats.csv        # only with --sample-system
  rosbag/                 # only with --bag
  trace/                  # only with --trace
```

`raw_samples.csv` contains:

- `timestamp`
- `seq`
- `send_time_ns`
- `receive_time_ns`
- `local_receive_monotonic_ns`
- `rtt_ns`
- `payload_size`
- `reordered`
- `duplicate`
- `lost_gap_detected`
- `gap_size`
- `timeout`

`summary.json` includes the aggregate metrics requested for the mode: sent/received counts, loss, duplicates, out-of-order count, throughput, RTT or one-way latency summaries, jitter, timeout count, discovery timing, and optional system metrics.

Post-run helpers:

```bash
ros2 run ros2_netbench summarize_run results/<run_id>
ros2 run ros2_netbench compare_runs results/run_a results/run_b --output comparison.md
```

## System Sampling

Enable local process and NIC sampling:

```bash
--sample-system --nic eth0
```

The sampler reads `/proc` directly. It reports current process CPU percent, process RSS memory, and interface TX/RX bps when the interface exists. Each role reports its own local metrics, for example sender-side CPU in the sender result directory and receiver-side CPU in the receiver result directory.

## Optional Bag and Tracing

Record benchmark topics:

```bash
--bag
```

Start ROS 2 tracing if installed:

```bash
--trace
```

These features shell out to `ros2 bag record` and `ros2 trace`. If the command is not installed, the runner fails with a clear error.

## Metric Interpretation

- `sent_messages`: messages or requests sent during the measurement phase. Stream receiver infers this from observed sequence range; the sender summary has the exact local sent count.
- `received_messages`: measurement-phase messages/replies/responses observed by the receiving role.
- `application_level_loss_count`: missing benchmark sequence numbers or missing replies/responses. This is not raw IP loss.
- `duplicate_count`: repeated sequence numbers received after already seeing the same sequence.
- `out_of_order_count`: non-duplicate sequence numbers that arrive lower than the highest sequence already observed.
- `throughput_messages_per_sec`: received or completed messages per measurement duration.
- `throughput_bytes_per_sec`: payload bytes per second, excluding ROS/DDS overhead.
- `RTT`: min/mean/std/p50/p90/p95/p99/max in milliseconds for ping and service clients.
- `one_way_latency`: same latency summary for stream receivers, valid only when clock sync is explicitly accepted.
- `inter_arrival_jitter_ms`: sample standard deviation of receiver inter-arrival periods.
- `publish_period_jitter_ms`: sample standard deviation of sender/client send periods.
- `receiver_gap_events`: number of online sequence jumps observed by a receiver.
- `timeout_count`: timed-out requests or discovery/first-packet timeout marker depending on role.

Warmup samples are excluded from final stats.

## Troubleshooting Discovery

If nodes do not connect:

1. Confirm both machines source the same built workspace and use the same `ROS_DOMAIN_ID`.
2. Check `RMW_IMPLEMENTATION` matches your intended middleware.
3. On same LAN, verify multicast is allowed and host firewalls permit DDS traffic.
4. Across networks, configure explicit discovery peers or a discovery server; do not rely on multicast.
5. Increase `--discovery-timeout 30` for routed/VPN links.
6. Use `ros2 node list`, `ros2 topic list`, and `ros2 service list` in the same environment.
7. Keep QoS compatible across endpoints.
8. Verify basic IP reachability with `ping`, `nc`, or your site’s approved network tools.

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
