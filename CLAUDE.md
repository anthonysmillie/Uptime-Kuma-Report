# CLAUDE.md

Guidance for Claude instances working in this repo. **This repo hosts TWO independent
scheduled reports** that share only their outbound-email plumbing and the cron dispatcher.
Despite the repo name ("Uptime-Kuma-Report"), the second report has nothing to do with
Uptime Kuma. Read this whole file before editing either report.

## The two reports

### 1. Uptime Kuma report — package `kuma_uptime_report/`
Pulls uptime data from an Uptime Kuma SQLite DB, renders charts (matplotlib/plotly) into
an HTML report, converts to PDF (weasyprint), and emails it via an external HTTP email API.
- Entry point: console script `kuma-uptime-report` (see `[project.scripts]`), source `kuma_uptime_report/cli.py` (click).
- Modes: `--weekly` / `--monthly` (previous calendar week/month), `--send-email`, `--include-html`.
- Config: `report_config.json` (sections/tags), `payload_config.json` (email template), `.env` (`DB_PATH`, `REPORT_PATH`, `API_*`).

### 2. Everlytic deliverability report — package `everlytic_deliverability_report/`
Renders Grafana panels for the previous week into a fixed Word (.docx) template, validates,
and emails the .docx. **Self-contained** — deliberately does NOT use python-docx or any
Claude office-skills plugin; docx surgery is stdlib `zipfile` + `lxml`.
- Entry point: `python -m everlytic_deliverability_report` (no console script, so no reinstall
  needed to deploy — just `git pull`; it imports as a top-level package from the repo root).
- Reuses report 1's email code: `kuma_uptime_report.email_send.{build_payload,send}` and
  `kuma_uptime_report.config.load_env`.
- Modes: `--weekly` (default; prev Mon→Sun in **SAST**), `--start/--end YYYY-MM-DD` (ad-hoc),
  `--send-email`, `--skip-delivery-validation`, `--output`, `--payload`.

#### How report 2 works (pipeline in `cli.py:main`)
1. Resolve the SAST week window (`dates.py`).
2. **Validate panels exist** (`validate.check_panels_exist`) via the Grafana dashboard API — structural, non-skippable.
3. **Render** all panels (`render.py`, playwright-python → headless Chromium screenshotting Grafana `/d-solo` views, auth via `Authorization: Bearer <SA token>`). The Grafana Image Renderer plugin is NOT installed, hence local rendering. Each panel is retried on transient Playwright/network errors (e.g. `net::ERR_NETWORK_CHANGED`) and on a stat value that fails to paint; tune with `RENDER_ATTEMPTS` (default 3) / `RENDER_BACKOFF_BASE` (default 3s). If a panel still fails after retries — or any other unexpected error occurs — a FAILED email is sent (when `--send-email`) instead of crashing silently.
4. **Validate renders non-empty** — structural, non-skippable.
5. **Delivery-volume band check** (`validate.check_delivery_band`) — skippable via `--skip-delivery-validation`.
6. **Compose** panels into slot images (`compose.py`, Pillow), **build** the docx (`docxbuild.py`), **verify**.
7. Email the docx, or (no `--send-email`) leave it in the output dir.

Any `ValidationFailure` → when `--send-email`, a "FAILED - …" email is sent with the reason
and re-run instructions (and the `--skip-delivery-validation` option only for the skippable
delivery check); exit code 1.

#### The report recipe lives in `everlytic_deliverability_report/panels.py`
This is the ONLY file to edit if Grafana changes. It holds: the two dashboard UIDs/slugs,
the panel→image-slot mapping (which panel IDs fill `word/media/imageN.png`), per-panel
render viewport sizes, composite layouts (row / 2×2 grid), the template's baked-in date
strings, protected media (cover + logos), and the delivery band (40M–60M).
Grafana panel IDs survive renames but change if a panel is deleted/rebuilt.

#### Recurring gotcha — the delivery band exists for a reason
Twice, MTA10 silently stopped shipping delivery logs to ClickHouse (a Vector issue), which
dropped Total Delivered Mails from ~44–50M to ~28–29M while the (Prometheus-based) SMTP-queue
panel still looked healthy. The band check catches this. If it fires, the fix is to restore
Vector log shipping to all three MTAs (mta9/mta10/mta11), then re-run. Grafana now also alerts
on per-srcMta log volume. Delivered volume = ClickHouse `count(distinct header_Message-ID)`.

## Shared plumbing
- **Email**: `kuma_uptime_report/email_send.py` (POST + HTTP Basic Auth to `$API_ENDPOINT`). Both reports build a payload from a JSON template and attach a base64 file.
- **`.env`** (repo root, git-ignored): `API_ENDPOINT/API_USERNAME/API_PASSWORD` (shared), plus for report 2: `GRAFANA_URL`, `GRAFANA_SERVICE_ACCOUNT_TOKEN` (SA needs org-Admin — the dashboards are in a permissioned "Delivery" folder), optional `REPORT_PATH`, `DELIVERABILITY_PAYLOAD_JSON`, `RUNNER_PATH`, `RENDER_ATTEMPTS`, `RENDER_BACKOFF_BASE`.
- **Payload templates**: `payload_config.json` (Kuma), `deliverability_payload_config.json` (deliverability). `.example` files are committed.
- **Cron dispatcher**: `generate_scheduled_report.sh <mode>` — activates the venv and runs one report. Modes: `weekly`, `monthly`, `weekly-html`, `monthly-html` (Kuma), `deliverability-weekly` (+ optional `--skip-delivery-validation` forwarded). **Each report is a SEPARATE cron entry** so one failing never blocks the other.

## Environment / deps
- Deployed on `dockerhost` at `/opt/KumaReport/NewKumaReport/Uptime-Kuma-Report`, **Debian 11 (bullseye), Python 3.9, uv-managed `.venv`**. Timezone is `Africa/Johannesburg` (report 2 still forces SAST via pytz regardless).
- Report 2 adds **playwright** (Python) + its **Chromium** browser. Chromium needs ~13 system libs (libnss3, libgbm1, libxkbcommon0, libasound2, libatk*, libcups2, libxcomposite1, libxdamage1, libxfixes3, libxrandr2, libnspr4, libatspi2.0-0) — install via `playwright install-deps chromium` or apt (root). `pyproject.toml` otherwise already provides lxml, Pillow (via matplotlib), requests, pytz, python-dotenv.
- To add the dep: `uv add playwright` then `.venv/bin/playwright install chromium` (+ install-deps once, as root).

## Running manually
```bash
cd /opt/KumaReport/NewKumaReport/Uptime-Kuma-Report && source .venv/bin/activate
# build only (no email), ad-hoc window:
python -m everlytic_deliverability_report --start 2026-08-24 --end 2026-08-30
# full scheduled run (what cron calls):
./generate_scheduled_report.sh deliverability-weekly
# after fixing a delivery-band false positive:
./generate_scheduled_report.sh deliverability-weekly --skip-delivery-validation
```

## Conventions
- Report 2 stamps the title page + version-table "Date of Update" with the **run/generation date** (`dd-mm-yyyy` / `dd/mm/yyyy`), and "Last Edited by" with the generic **"Report Automation"**. The **output filename** uses the reporting week's **Sunday** (week-end) date, so files stay identifiable by the week they cover.
- Keep report 2 dependency-light and self-contained; do not reintroduce a dependency on the office-skills plugin.
- Secrets only in `.env`, never committed.
