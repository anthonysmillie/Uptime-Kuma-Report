"""Validation checks and the failure type carried through to the FAILED email.

Two classes of failure:
  * structural (skippable=False): panel IDs no longer exist, or a render came back
    empty/too small. A broken report must NOT be produced or sent.
  * delivery band (skippable=True): Total Delivered Mails outside the expected range,
    the recurring "an MTA stopped shipping logs" symptom. Skippable via
    --skip-delivery-validation once a human has verified in Grafana.
"""
import os
import re
from typing import Dict, List, Tuple

import requests


class ValidationFailure(Exception):
    def __init__(self, title: str, detail_html: str, skippable: bool):
        super().__init__(title)
        self.title = title
        self.detail_html = detail_html   # one or more <li> bullets
        self.skippable = skippable


_MULT = {"bil": 1e9, "mil": 1e6, "k": 1e3, "": 1.0}


def parse_stat_value(text: str) -> float:
    """'45.9 Mil' -> 45900000.0 ; '253 K' -> 253000.0 ; '12345' -> 12345.0."""
    if not text:
        raise ValueError("empty stat value")
    m = re.match(r"^\s*([\d.,]+)\s*(Bil|Mil|K)?\s*$", text, re.IGNORECASE)
    if not m:
        raise ValueError(f"unparseable stat value: {text!r}")
    num = float(m.group(1).replace(",", ""))
    return num * _MULT[(m.group(2) or "").lower()]


def _dashboard_panel_ids(grafana_url: str, token: str, uid: str) -> set:
    resp = requests.get(
        f"{grafana_url.rstrip('/')}/api/dashboards/uid/{uid}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    dash = resp.json().get("dashboard", {})
    ids = set()

    def walk(panels):
        for p in panels:
            if "id" in p:
                ids.add(p["id"])
            if p.get("type") == "row" and p.get("panels"):
                walk(p["panels"])

    walk(dash.get("panels", []))
    return ids


def check_panels_exist(grafana_url: str, token: str, dashboards: Dict[str, dict],
                       required: List[Tuple[str, int]]) -> None:
    """Raise a structural ValidationFailure listing any required panel IDs that are gone."""
    needed_by_dash: Dict[str, set] = {}
    for dash_key, pid in required:
        needed_by_dash.setdefault(dash_key, set()).add(pid)

    missing: List[str] = []
    for dash_key, pids in needed_by_dash.items():
        dash = dashboards[dash_key]
        present = _dashboard_panel_ids(grafana_url, token, dash["uid"])
        for pid in sorted(pids):
            if pid not in present:
                missing.append(f"panel id {pid} on dashboard \"{dash['slug']}\" ({dash_key})")

    if missing:
        bullets = "".join(f"<li>Missing {m}.</li>" for m in missing)
        raise ValidationFailure(
            title="Grafana panel(s) missing",
            detail_html=(
                "<li>One or more panels the report depends on no longer exist in Grafana "
                "(renamed/rebuilt/deleted). The report cannot be generated until the panel "
                "mapping is corrected.</li>" + bullets +
                "<li><b>This is a structural error and cannot be skipped.</b> Update panel IDs "
                "in <code>everlytic_deliverability_report/panels.py</code>.</li>"
            ),
            skippable=False,
        )


def check_renders_nonempty(out_dir: str, jobs: List[dict], min_bytes: int = 2048) -> None:
    """Raise a structural ValidationFailure if any render is missing or suspiciously tiny."""
    bad: List[str] = []
    for job in jobs:
        path = os.path.join(out_dir, job["outfile"])
        if not os.path.exists(path) or os.path.getsize(path) < min_bytes:
            bad.append(f"panel id {job['id']} (dashboard {job['dash']})")
    if bad:
        bullets = "".join(f"<li>Empty/failed render for {b}.</li>" for b in bad)
        raise ValidationFailure(
            title="Panel render failed",
            detail_html=("<li>One or more panels rendered empty. Grafana may be unreachable, "
                         "the datasource down, or the panel broken.</li>" + bullets +
                         "<li><b>Structural error, cannot be skipped.</b></li>"),
            skippable=False,
        )


def check_delivery_band(captured: Dict[str, str], cfg: dict) -> None:
    """Raise a skippable ValidationFailure if Total Delivered Mails is outside the band."""
    text = captured.get(cfg["capture"])
    low, high, label = cfg["low"], cfg["high"], cfg["label"]

    def fmt(n):
        return f"{n/1_000_000:.0f}M"

    if not text:
        raise ValidationFailure(
            title="Delivered-mail value unreadable",
            detail_html=(f"<li>Could not read the <b>{label}</b> value from the rendered panel, "
                         "so the volume sanity check could not run.</li>"),
            skippable=True,
        )
    value = parse_stat_value(text)
    if not (low <= value <= high):
        raise ValidationFailure(
            title="Delivered-mail volume out of range",
            detail_html=(
                f"<li>The expected volume range for delivered mail should be between "
                f"<b>{fmt(low)}</b> and <b>{fmt(high)}</b>. The current amount of delivered mail "
                f"for this period, as shown in Grafana, is <b>{text} (~{fmt(value)})</b>. "
                "Please check to ensure that Vector is still shipping logs to all 3 MTAs "
                "(mta9/mta10/mta11) as expected.</li>"
            ),
            skippable=True,
        )
