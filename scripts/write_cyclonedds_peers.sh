#!/usr/bin/env bash
set -euo pipefail

OUTPUT="${OUTPUT:-cyclonedds-peers.xml}"
INTERFACE_ADDRESS="${INTERFACE_ADDRESS:-}"
PEERS="${PEERS:-}"

if [[ -z "${PEERS}" ]]; then
  cat >&2 <<EOF
Usage:
  PEERS=100.64.0.11,100.64.0.12 INTERFACE_ADDRESS=100.64.0.10 \\
    OUTPUT=cyclonedds-peers.xml scripts/write_cyclonedds_peers.sh

Set INTERFACE_ADDRESS to this machine's reachable address on the tailnet/VPN.
Set PEERS to the other machine address or a comma-separated list of peer addresses.
EOF
  exit 2
fi

if [[ -z "${INTERFACE_ADDRESS}" ]]; then
  echo "INTERFACE_ADDRESS is required so Cyclone DDS advertises the intended interface." >&2
  exit 2
fi

{
  cat <<EOF
<?xml version="1.0" encoding="utf-8"?>
<CycloneDDS>
  <Domain Id="any">
    <General>
      <NetworkInterfaceAddress>${INTERFACE_ADDRESS}</NetworkInterfaceAddress>
      <AllowMulticast>false</AllowMulticast>
    </General>
    <Discovery>
      <Peers>
EOF
  IFS=',' read -ra peer_items <<< "${PEERS}"
  for peer in "${peer_items[@]}"; do
    peer="${peer#"${peer%%[![:space:]]*}"}"
    peer="${peer%"${peer##*[![:space:]]}"}"
    [[ -z "${peer}" ]] && continue
    printf '        <Peer Address="%s"/>\n' "${peer}"
  done
  cat <<EOF
      </Peers>
    </Discovery>
  </Domain>
</CycloneDDS>
EOF
} > "${OUTPUT}"

echo "[ros2_netbench] wrote ${OUTPUT}" >&2
echo "[ros2_netbench] export CYCLONEDDS_URI=file://$(cd "$(dirname "${OUTPUT}")" && pwd)/$(basename "${OUTPUT}")" >&2
