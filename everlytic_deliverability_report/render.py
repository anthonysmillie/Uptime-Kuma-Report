"""Render Grafana panels to PNG via headless Chromium (playwright-python).

The official Grafana Image Renderer plugin is NOT installed on the instance, so we
screenshot each panel's `/d-solo` single-panel view, authenticated with the service
account token. Ported from the proven Node pipeline.
"""
import os
from typing import Dict, List

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

# A big-font numeric span having painted means the stat panel's value/threshold is ready.
_STAT_READY_JS = r"""() => {
  for (const e of document.querySelectorAll('span,div')) {
    const t = (e.textContent || '').trim();
    if (/^[\d.,]+\s*(Mil|K|Bil)?$/.test(t) && parseFloat(t) &&
        parseFloat(getComputedStyle(e).fontSize) > 28) return true;
  }
  return false;
}"""

_READ_VALUE_JS = r"""() => {
  let best = null, bestFs = 0;
  for (const e of document.querySelectorAll('span,div')) {
    const t = (e.textContent || '').trim();
    if (/^[\d.,]+\s*(Mil|K|Bil)?$/.test(t) && parseFloat(t)) {
      const fs = parseFloat(getComputedStyle(e).fontSize);
      if (fs > bestFs) { bestFs = fs; best = t; }
    }
  }
  return best;
}"""


def render_all(grafana_url: str, token: str, from_ms: int, to_ms: int,
               out_dir: str, jobs: List[dict], dashboards: Dict[str, dict],
               timezone: str = "Africa/Johannesburg") -> Dict[str, str]:
    """Render every job to out_dir/<outfile>. Returns {capture_tag: value_text} for
    panels flagged with `capture` (e.g. {"delivered": "45.9 Mil"})."""
    os.makedirs(out_dir, exist_ok=True)
    captured: Dict[str, str] = {}
    grafana_url = grafana_url.rstrip("/")

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for job in jobs:
                dash = dashboards[job["dash"]]
                ctx = browser.new_context(
                    viewport={"width": job["vw"], "height": job["vh"]},
                    device_scale_factor=2,
                    extra_http_headers={"Authorization": f"Bearer {token}"},
                )
                page = ctx.new_page()
                url = (f"{grafana_url}/d-solo/{dash['uid']}/{dash['slug']}"
                       f"?panelId={job['id']}&from={from_ms}&to={to_ms}"
                       f"&theme=light&timezone={timezone}")
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                if job.get("stat"):
                    try:
                        page.wait_for_function(_STAT_READY_JS, timeout=20000)
                    except PWTimeout:
                        pass
                    page.wait_for_timeout(1500)
                    if job.get("capture"):
                        captured[job["capture"]] = page.evaluate(_READ_VALUE_JS)
                else:
                    page.wait_for_timeout(4000)
                page.screenshot(path=os.path.join(out_dir, job["outfile"]))
                ctx.close()
        finally:
            browser.close()
    return captured
