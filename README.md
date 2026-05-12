# Uptime-Kuma-Report

Generate uptime reports from an Uptime Kuma SQLite database. Produces an interactive
HTML report (Plotly), an optional static PDF (WeasyPrint + matplotlib), and can POST
the PDF to an HTTP email API.

## Installation

The project ships a `pyproject.toml` and is managed with [uv](https://docs.astral.sh/uv/).

```bash
# Development install
uv sync

# System-wide install via pipx (recommended for the cron host)
pipx install /path/to/Uptime-Kuma-Report
```

After install the `kuma-uptime-report` command is on `$PATH`.

### System dependencies for the PDF/email path

WeasyPrint pulls in cairo, pango, and gdk-pixbuf at runtime.

- **Debian/Ubuntu:** `apt install libcairo2 libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf2.0-0`
- **macOS (Homebrew):** `brew install cairo pango gdk-pixbuf`
  - You may also need `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` exported for cairocffi to find the dylibs.

If you only need the interactive HTML report (no `--pdf`, no `--send-email`), these
system libraries are not required.

## Modes

The CLI runs in one of two modes, decided by whether `-c` and `-t` are passed:

| Flags                | Mode             | Behavior                                                |
| -------------------- | ---------------- | ------------------------------------------------------- |
| Both `-c` and `-t`   | Single-section   | One chart, like the legacy CLI. `report_config.json` is ignored. |
| Neither              | Multi-section    | Reads `report_config.json` and emits one document with N charts. |
| Only one of them     | **Error**        | Passing only `-c` or only `-t` is rejected.             |

## CLI options

| Flag                                          | Required | Notes |
| --------------------------------------------- | -------- | ----- |
| `--db PATH`                                   | yes¹     | Path to the Uptime Kuma SQLite database. Falls back to `$DB_PATH` from `.env`.                                 |
| `-d, --days INT`                              | one of   | Rolling window of N days ending now. Good for ad-hoc reports.                                                  |
| `--weekly`                                    | one of   | The previous calendar week (Mon 00:00 → next Mon 00:00). Independent of run time.                              |
| `--monthly`                                   | one of   | The previous calendar month (1st 00:00 → 1st of this month 00:00). Independent of run time.                    |
| `--start YYYY-MM-DD` / `--end YYYY-MM-DD`     | one of   | Explicit date range (alternative to the above).                                                                |
| `-c, --caption TEXT`                          | paired   | Single-section chart title. Must be passed with `-t`.                                                          |
| `-t, --tag TEXT`                              | paired   | Single-section monitor tag. Must be passed with `-c`.                                                          |
| `--min-y INT`                                 | no       | Minimum y-axis value. Overrides `global_settings.min_y` in the config.                                         |
| `--config / --report-config PATH`             | no       | Path to `report_config.json`. Overrides `$REPORT_JSON`.                                                        |
| `--payload / --payload-config PATH`           | no       | Path to `payload_config.json`. Overrides `$PAYLOAD_JSON`.                                                      |
| `-o, --output DIR`                            | no       | Output directory (both HTML and PDF land here). Overrides `$REPORT_PATH`.                                      |
| `--pdf`                                       | no       | Also render a PDF copy. No email is sent.                                                                      |
| `--send-email`                                | no       | Render a PDF and POST it to `$API_ENDPOINT` using basic auth. PDF is also saved to disk.                       |
| `--help`                                      |          | Show full help.                                                                                                |

¹ Required either on the CLI or as `DB_PATH` in `.env`.

## Output location

Either `-o` or `REPORT_PATH` (in `.env`) must be set; otherwise the CLI errors out.

- **`-o DIR`** — both HTML and PDF dropped into `DIR/`, flat.
- **`REPORT_PATH=/opt/KumaReport/Reports`** — HTML goes to `$REPORT_PATH/html/`, PDF
  goes to `$REPORT_PATH/pdf/`. Subdirectories are created automatically.

Filenames are `UptimeKumaReport_<days>-Days_<dd-mm-yyyy>.<ext>`, with `_2`, `_3`, …
appended before the extension on collision (useful when re-running on the same day).

## Configuration files

### `report_config.json` — multi-section layout

Search order: `--config` flag → `$REPORT_JSON` env → `./report_config.json` in CWD.

```json
{
  "global_settings": { "min_y": 80 },
  "header": { "name": "UptimeKuma Uptime Report", "tag": "Parents" },
  "sections": [
    { "name": "UptimeKuma API Uptime",              "tag": "api" },
    { "name": "UptimeKuma Custom Hostnames Uptime", "tag": "hostnames" },
    { "name": "UptimeKuma Live Installs Uptime",    "tag": "live" },
    { "name": "UptimeKuma MTA Uptime",              "tag": "mta" }
  ]
}
```

- `header` is the first section and supplies the report title. Its caption is auto-decorated
  as `"<name> - <days> Days - <start> to <end>"`.
- `sections[].name` is auto-decorated as `"<name> - <days> Days"`.
- Tags must match `tag.name` values in your Uptime Kuma DB.

### `payload_config.json` — email payload template

Search order: `--payload` flag → `$PAYLOAD_JSON` env → `./payload_config.json` in CWD.

```json
{
  "body":    { "text": "Please find the latest Uptime Kuma report attached." },
  "headers": {
    "subject": "Uptime Kuma Report",
    "from":    { "email": "sender@example.com",    "name": "Uptime Kuma Reports" },
    "to":      [{ "email": "recipient@example.com", "name": "Recipient Name" }]
  },
  "attachments": { "data": [{ "filename": "report.pdf", "data": "" }] }
}
```

The CLI mutates this template at send time:
- `attachments.data[0].data` ← base64 of the generated PDF.
- `attachments.data[0].filename` ← the PDF's basename.
- `headers.subject` gets ` - <days> Days - <dd/mm/yyyy>-<dd/mm/yyyy>` appended.

### `.env` — secrets and defaults

Loaded from `./.env` via [python-dotenv](https://pypi.org/project/python-dotenv/).

```dotenv
API_ENDPOINT=https://mail-api.example.com/send
API_USERNAME=your-username
API_PASSWORD=your-password

# Optional default DB path used when --db is omitted.
# DB_PATH=/opt/docker-mounts/uptimekuma/kuma.db

# Optional default output location used when -o is omitted.
# REPORT_PATH=/opt/KumaReport/Reports

# Optional: point at config files outside the working directory.
# REPORT_JSON=/opt/KumaReport/report_config.json
# PAYLOAD_JSON=/opt/KumaReport/payload_config.json
```

## Examples

```bash
# Multi-section weekly report → HTML only, written to $REPORT_PATH/html.
# (Assumes DB_PATH and REPORT_PATH are set in .env.)
kuma-uptime-report -d 7

# Multi-section + PDF, written to an ad-hoc directory.
kuma-uptime-report --db kuma.db -d 7 --pdf -o /tmp/this-week

# Multi-section + PDF + email via the API (typical cron invocation).
kuma-uptime-report -d 7 --send-email

# Single-section ad-hoc report (skips report_config.json entirely).
kuma-uptime-report --db kuma.db -d 30 -c "API uptime - last 30 days" -t api -o /tmp/api-report

# Custom date range.
kuma-uptime-report --db kuma.db --start 2026-04-01 --end 2026-04-30 --pdf
```

## Cron usage

A minimal wrapper for cron is needed only to set the working directory (where `.env`
and the config JSONs live) and, on macOS, `DYLD_FALLBACK_LIBRARY_PATH`:

```bash
#!/bin/bash
cd /opt/KumaReport
kuma-uptime-report -d 7 --send-email
```

(`DB_PATH` and `REPORT_PATH` in `.env` cover everything else.)

The previous 8-invocation bash wrapper that concatenated HTML fragments and emailed
via the local MTA is no longer needed.
