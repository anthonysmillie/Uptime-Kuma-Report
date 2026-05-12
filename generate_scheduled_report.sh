#!/bin/bash
set -euo pipefail
MODE="${MODE:-${1:-weekly}}"     # "weekly" or "monthly"
runner_path="/opt/KumaReport/NewKumaReport/Uptime-Kuma-Report"

cd "$runner_path"
source "$runner_path/.venv/bin/activate"

case "$MODE" in
  weekly)  kuma-uptime-report -d 7 --send-email ;;
  monthly) kuma-uptime-report --monthly --send-email ;;
  *) echo "Unknown mode: $MODE (expected 'weekly' or 'monthly')" >&2; exit 2 ;;
esac