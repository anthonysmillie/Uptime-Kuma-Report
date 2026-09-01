#!/bin/bash
set -euo pipefail
# Dispatches the scheduled reports. Called from cron, one invocation per report.
# The Kuma uptime report and the Everlytic deliverability report are independent:
# run them as separate cron entries so a validation failure in one never blocks the other.
MODE="${MODE:-${1:-weekly}}"
runner_path="/opt/KumaReport/NewKumaReport/Uptime-Kuma-Report"

cd "$runner_path"
source "$runner_path/.venv/bin/activate"

case "$MODE" in
  # --- Uptime Kuma report (kuma_uptime_report) ---
  weekly)       kuma-uptime-report --weekly  --send-email ;;
  monthly)      kuma-uptime-report --monthly --send-email ;;
  weekly-html)  kuma-uptime-report --weekly  --send-email --include-html ;;
  monthly-html) kuma-uptime-report --monthly --send-email --include-html ;;
  # --- Everlytic deliverability report (everlytic_deliverability_report) ---
  # Extra args after the mode are forwarded, e.g. `... deliverability-weekly --skip-delivery-validation`.
  deliverability-weekly)
    python -m everlytic_deliverability_report --weekly --send-email "${@:2}" ;;
  *) echo "Unknown mode: $MODE (expected 'weekly', 'monthly', 'weekly-html', 'monthly-html', or 'deliverability-weekly')" >&2; exit 2 ;;
esac