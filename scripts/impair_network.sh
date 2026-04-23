#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  impair_network.sh show <iface>
  impair_network.sh clear <iface>
  impair_network.sh apply <iface> [options]

Options for apply:
  --latency-ms N       Add fixed latency
  --jitter-ms N        Add latency jitter
  --loss-pct N         Drop percentage
  --duplicate-pct N    Duplicate percentage
  --reorder-pct N      Reorder percentage
  --rate M            Rate limit, e.g. 10mbit, 1000kbit

Examples:
  sudo scripts/impair_network.sh apply eth0 --latency-ms 40 --jitter-ms 5 --loss-pct 1
  sudo scripts/impair_network.sh apply eth0 --rate 10mbit
  scripts/impair_network.sh show eth0
  sudo scripts/impair_network.sh clear eth0
EOF
}

if [[ $# -lt 2 ]]; then
  usage
  exit 2
fi

ACTION="$1"
IFACE="$2"
shift 2

case "${ACTION}" in
  show)
    tc qdisc show dev "${IFACE}"
    ;;
  clear)
    tc qdisc del dev "${IFACE}" root 2>/dev/null || true
    tc qdisc show dev "${IFACE}"
    ;;
  apply)
    LATENCY_MS=""
    JITTER_MS=""
    LOSS_PCT=""
    DUPLICATE_PCT=""
    REORDER_PCT=""
    RATE=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --latency-ms) LATENCY_MS="$2"; shift 2 ;;
        --jitter-ms) JITTER_MS="$2"; shift 2 ;;
        --loss-pct) LOSS_PCT="$2"; shift 2 ;;
        --duplicate-pct) DUPLICATE_PCT="$2"; shift 2 ;;
        --reorder-pct) REORDER_PCT="$2"; shift 2 ;;
        --rate) RATE="$2"; shift 2 ;;
        *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
      esac
    done

    NETEM=(netem)
    if [[ -n "${LATENCY_MS}" ]]; then
      NETEM+=(delay "${LATENCY_MS}ms")
      if [[ -n "${JITTER_MS}" ]]; then
        NETEM+=("${JITTER_MS}ms")
      fi
    fi
    if [[ -n "${LOSS_PCT}" ]]; then
      NETEM+=(loss "${LOSS_PCT}%")
    fi
    if [[ -n "${DUPLICATE_PCT}" ]]; then
      NETEM+=(duplicate "${DUPLICATE_PCT}%")
    fi
    if [[ -n "${REORDER_PCT}" ]]; then
      NETEM+=(reorder "${REORDER_PCT}%" "50%")
    fi
    if [[ -n "${RATE}" ]]; then
      NETEM+=(rate "${RATE}")
    fi

    tc qdisc replace dev "${IFACE}" root "${NETEM[@]}"
    tc qdisc show dev "${IFACE}"
    ;;
  *)
    usage
    exit 2
    ;;
esac
