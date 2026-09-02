"""Render Grafana panels to PNG via headless Chromium (playwright-python).

The official Grafana Image Renderer plugin is NOT installed on the instance, so we
screenshot each panel's `/d-solo` single-panel view, authenticated with the service
account token. Ported from the proven Node pipeline.

Each panel render is retried on transient Playwright/network errors (e.g.
net::ERR_NETWORK_CHANGED, connection resets, nav timeouts) so a momentary blip does
not abort the whole report. Tunable via env RENDER_ATTEMPTS / RENDER_BACKOFF_BASE.
"""
import os
import sys
import time
from typing import Dict, List

from playwright.sync_api import Error as PWError
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


class TransientRenderError(Exception):
    """A soft render miss worth retrying (e.g. a stat value that didn't paint in time)."""


def _log(msg: str) -> None:
    sys.stderr.write(f"[deliverability-report] {msg}\n")
    sys.stderr.flush()


def _attempts() -> int:
    return max(1, int(os.environ.get("RENDER_ATTEMPTS", "3")))


def _backoff_base() -> float:
    return float(os.environ.get("RENDER_BACKOFF_BASE", "3"))


def _retry(label: str, fn):
    """Call fn(), retrying on transient Playwright errors with linear backoff.

    Raises RuntimeError if all attempts fail (so the caller can surface it cleanly).
    """
    attempts = _attempts()
    last = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except (PWError, TransientRenderError) as e:
            last = e
            first_line = str(e).splitlines()[0]
            if attempt < attempts:
                wait = attempt * _backoff_base()
                _log(f"{label} attempt {attempt}/{attempts} failed ({first_line}); retrying in {wait:g}s")
                time.sleep(wait)
            else:
                _log(f"{label} failed after {attempts} attempts ({first_line})")
    raise RuntimeError(f"{label} failed after {attempts} attempts: {last}")


def _render_job(browser, job: dict, grafana_url: str, token: str,
                from_ms: int, to_ms: int, timezone: str, out_dir: str):
    """Render a single panel (fresh context each call so a retry starts clean).
    Returns the captured value text (for stat panels) or None."""
    dash = job["_dash"]
    url = (f"{grafana_url}/d-solo/{dash['uid']}/{dash['slug']}"
           f"?panelId={job['id']}&from={from_ms}&to={to_ms}"
           f"&theme=light&timezone={timezone}")
    ctx = browser.new_context(
        viewport={"width": job["vw"], "height": job["vh"]},
        device_scale_factor=2,
        extra_http_headers={"Authorization": f"Bearer {token}"},
    )
    try:
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=40000)
        value = None
        if job.get("stat"):
            try:
                page.wait_for_function(_STAT_READY_JS, timeout=20000)
            except PWError:
                pass  # value didn't paint in time; screenshot proceeds regardless
            page.wait_for_timeout(1500)
            if job.get("capture"):
                value = page.evaluate(_READ_VALUE_JS)
                if value is None:
                    # stat didn't paint in time; retry the whole panel for another shot
                    raise TransientRenderError(
                        f"captured value for panel {job['id']} did not paint")
        else:
            page.wait_for_timeout(4000)
        page.screenshot(path=os.path.join(out_dir, job["outfile"]))
        return value
    finally:
        ctx.close()


def render_all(grafana_url: str, token: str, from_ms: int, to_ms: int,
               out_dir: str, jobs: List[dict], dashboards: Dict[str, dict],
               timezone: str = "Africa/Johannesburg") -> Dict[str, str]:
    """Render every job to out_dir/<outfile>, retrying transient failures per panel.
    Returns {capture_tag: value_text} for panels flagged with `capture`."""
    os.makedirs(out_dir, exist_ok=True)
    grafana_url = grafana_url.rstrip("/")
    captured: Dict[str, str] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for job in jobs:
                job = dict(job, _dash=dashboards[job["dash"]])
                value = _retry(
                    f"panel {job['id']} (dashboard {job['dash']})",
                    lambda job=job: _render_job(browser, job, grafana_url, token,
                                                from_ms, to_ms, timezone, out_dir),
                )
                if job.get("capture"):
                    captured[job["capture"]] = value
        finally:
            browser.close()
    return captured
