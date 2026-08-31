#!/bin/bash
set -euo pipefail
MODE="${MODE:-${1:-weekly}}"     # "weekly" or "monthly"
runner_path="/opt/KumaReport/NewKumaReport/Uptime-Kuma-Report"

cd "$runner_path"
source "$runner_path/.venv/bin/activate"

case "$MODE" in
  weekly)       kuma-uptime-report --weekly  --send-email ;;
  monthly)      kuma-uptime-report --monthly --send-email ;;
  weekly-html)  kuma-uptime-report --weekly  --send-email --include-html ;;
  monthly-html) kuma-uptime-report --monthly --send-email --include-html ;;
  *) echo "Unknown mode: $MODE (expected 'weekly', 'monthly', 'weekly-html', or 'monthly-html')" >&2; exit 2 ;;
esac