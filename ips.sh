#!/usr/bin/env bash
# Source this on both devices before running scripts/run_cross_network.sh.
# Device B is the receiver and Fast DDS discovery server by default.

_ips_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export DEVICE_A="${DEVICE_A:-100.92.111.95}"
export DEVICE_B="${DEVICE_B:-100.118.2.108}"
export DISCOVERY_PORT="${DISCOVERY_PORT:-11811}"
export DISCOVERY_DEVICE="${DISCOVERY_DEVICE:-$DEVICE_B}"

_tailscale_ip=""
if command -v tailscale >/dev/null 2>&1; then
  _tailscale_ip="$(tailscale ip -4 2>/dev/null | head -n 1 || true)"
fi

if [[ -z "$_tailscale_ip" ]]; then
  for _candidate in $DEVICE_A $DEVICE_B; do
    if hostname -I 2>/dev/null | tr ' ' '\n' | grep -qx "$_candidate"; then
      _tailscale_ip="$_candidate"
      break
    fi
  done
fi

export LOCAL_TAILSCALE_IP="${LOCAL_TAILSCALE_IP:-$_tailscale_ip}"

if [[ "$LOCAL_TAILSCALE_IP" == "$DEVICE_A" ]]; then
  export ROLE="${ROLE:-sender}"
  export OUTPUT_DIR="${OUTPUT_DIR:-results/cross_tx}"
elif [[ "$LOCAL_TAILSCALE_IP" == "$DEVICE_B" ]]; then
  export ROLE="${ROLE:-receiver}"
  export OUTPUT_DIR="${OUTPUT_DIR:-results/cross_rx}"
else
  export ROLE="${ROLE:-receiver}"
  export OUTPUT_DIR="${OUTPUT_DIR:-results/cross_rx}"
  echo "ips.sh: could not match this host to DEVICE_A or DEVICE_B; set LOCAL_TAILSCALE_IP if needed" >&2
fi

export ROS_DISCOVERY_SERVER="${ROS_DISCOVERY_SERVER:-$DISCOVERY_DEVICE:$DISCOVERY_PORT}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export SESSION_ID="${SESSION_ID:-4242}"
export DURATION="${DURATION:-30}"
export WARMUP="${WARMUP:-3}"
export RATE_HZ="${RATE_HZ:-100}"
export PAYLOAD_SIZE="${PAYLOAD_SIZE:-1024}"

if [[ -n "$LOCAL_TAILSCALE_IP" ]]; then
  _fastdds_profile="${FASTDDS_TAILSCALE_PROFILE:-$_ips_dir/.fastdds_tailscale.xml}"
  cat >"$_fastdds_profile" <<EOF
<?xml version="1.0" encoding="UTF-8" ?>
<profiles xmlns="http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles">
  <transport_descriptors>
    <transport_descriptor>
      <transport_id>tailscale_udp</transport_id>
      <type>UDPv4</type>
      <interfaceWhiteList>
        <address>$LOCAL_TAILSCALE_IP</address>
      </interfaceWhiteList>
    </transport_descriptor>
  </transport_descriptors>
  <participant profile_name="tailscale_participant" is_default_profile="true">
    <rtps>
      <userTransports>
        <transport_id>tailscale_udp</transport_id>
      </userTransports>
      <useBuiltinTransports>false</useBuiltinTransports>
    </rtps>
  </participant>
</profiles>
EOF
  export FASTRTPS_DEFAULT_PROFILES_FILE="$_fastdds_profile"
  export FASTDDS_DEFAULT_PROFILES_FILE="$_fastdds_profile"
fi

echo "ips.sh: local=${LOCAL_TAILSCALE_IP:-unknown} role=$ROLE discovery=$ROS_DISCOVERY_SERVER profile=${FASTRTPS_DEFAULT_PROFILES_FILE:-none}" >&2
