#!/usr/bin/env bash
set -euo pipefail

MODE="${MODE:-stream}"
ROLE="${ROLE:-receiver}"
OUTPUT_DIR="${OUTPUT_DIR:-results}"
PAYLOAD_SIZE="${PAYLOAD_SIZE:-1024}"
RATE_HZ="${RATE_HZ:-10}"
DURATION="${DURATION:-10}"
WARMUP="${WARMUP:-2}"
RELIABILITY="${RELIABILITY:-reliable}"
DEPTH="${DEPTH:-10}"

exec ros2 run ros2_netbench run_benchmark \
  --mode "${MODE}" \
  --role "${ROLE}" \
  --payload-size "${PAYLOAD_SIZE}" \
  --rate-hz "${RATE_HZ}" \
  --duration "${DURATION}" \
  --warmup "${WARMUP}" \
  --output-dir "${OUTPUT_DIR}" \
  --reliability "${RELIABILITY}" \
  --depth "${DEPTH}" \
  "$@"
