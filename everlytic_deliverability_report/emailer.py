"""Outbound email: success (report attached) and FAILED (validation error) paths.

Reuses the Uptime-Kuma email API plumbing so both reports go out the same way,
with the same credentials/sender/recipients — just a different payload template.
"""
import copy
from pathlib import Path
from typing import List

from kuma_uptime_report.email_send import build_payload, send

from .validate import ValidationFailure


def send_success(template: dict, docx_path: str, window):
    """Attach the report and POST it. Subject becomes '<base> - dd/mm/yyyy-dd/mm/yyyy'."""
    payload = build_payload(template, [docx_path], None, window.start, window.end)
    return send(payload)


def _failure_html(window, failures: List[ValidationFailure], runner: str) -> str:
    bullets = "".join(f.detail_html for f in failures)
    skip_block = ""
    if any(f.skippable for f in failures):
        skip_block = (
            "<p>Should you believe the above to be a false positive result, and you have "
            "verified the count within Grafana and have ensured that Vector is shipping logs "
            "as expected, please re-run the report using the following command:</p>"
            f"<p><code>{runner} deliverability-weekly --skip-delivery-validation</code></p>"
        )
    return (
        "<html><body>"
        f"<p>The Everlytic Weekly Deliverability Report ({window.subject_range}) failed to "
        "send due to the following validation error(s):</p>"
        f"<ul>{bullets}</ul>"
        "<p>Once the above error has been resolved, please re-run the report on the dockerhost "
        "as root, using the following command:</p>"
        f"<p><code>{runner} deliverability-weekly</code></p>"
        f"{skip_block}"
        "</body></html>"
    )


def send_failure(template: dict, window, failures: List[ValidationFailure], runner: str):
    """Send a FAILED notification (no attachment) explaining why and how to re-run."""
    base_subject = template.get("headers", {}).get("subject", "Everlytic Weekly Deliverability Report")
    payload = copy.deepcopy(template)
    payload.setdefault("headers", {})["subject"] = f"FAILED - {base_subject}"
    payload.setdefault("body", {})["html"] = _failure_html(window, failures, runner)
    payload["attachments"] = {"data": []}
    return send(payload)
