#!/usr/bin/env bash
set -euo pipefail

REMOTE="${1:-}"
MAX_OFFSET_MS="${MAX_OFFSET_MS:-1.0}"

cat <<EOF
Local time:
  date -Ins: $(date -Ins)
  timedatectl:
$(timedatectl 2>/dev/null | sed 's/^/    /' || true)
EOF

if command -v chronyc >/dev/null 2>&1; then
  echo
  echo "chronyc tracking:"
  chronyc tracking || true
fi

if [[ -n "${REMOTE}" ]]; then
  echo
  echo "Remote check via ssh (${REMOTE}):"
  ssh "${REMOTE}" 'date -Ins; timedatectl 2>/dev/null | sed "s/^/  /" || true'
  cat <<EOF

Compare chrony/NTP status on both machines. For one-way latency summaries, run
with --clock-sync ok only when the absolute offset is comfortably below
${MAX_OFFSET_MS} ms, or run with --clock-sync offset --clock-offset-ms <receiver_minus_sender_ms>.
EOF
else
  cat <<EOF

Pass user@host to also print the remote clock status:
  scripts/sync_clock_check.sh robot@192.0.2.20

One-way latency is disabled by default. Enable it only after validating clock
sync:
  --clock-sync ok
or provide a measured receiver-minus-sender offset:
  --clock-sync offset --clock-offset-ms 0.42
EOF
fi
