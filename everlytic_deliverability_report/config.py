"""Config & environment resolution for the deliverability report.

Reuses the Uptime-Kuma project's .env loading so both reports share one .env
(API_ENDPOINT/USERNAME/PASSWORD for the email API). Adds the Grafana settings this
report needs. All secrets live in the repo-root .env (git-ignored), never in code.
"""
import json
import os
from pathlib import Path

from kuma_uptime_report.config import load_env  # shared .env loader

DEFAULT_PAYLOAD_FILENAME = "deliverability_payload_config.json"
DEFAULT_RUNNER_PATH = "/opt/KumaReport/NewKumaReport/Uptime-Kuma-Report"


def init_env() -> None:
    load_env()


def grafana_creds():
    url = os.environ.get("GRAFANA_URL")
    token = os.environ.get("GRAFANA_SERVICE_ACCOUNT_TOKEN")
    missing = [k for k, v in {"GRAFANA_URL": url, "GRAFANA_SERVICE_ACCOUNT_TOKEN": token}.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing required env vars: {', '.join(missing)}. "
            "Add them to the repo-root .env."
        )
    return url.rstrip("/"), token


def load_payload_template(cli_path=None) -> dict:
    path = cli_path or os.environ.get("DELIVERABILITY_PAYLOAD_JSON") \
        or (Path.cwd() / DEFAULT_PAYLOAD_FILENAME)
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Deliverability payload config not found at {path}. "
            f"Copy {DEFAULT_PAYLOAD_FILENAME}.example and fill it in, or set "
            "DELIVERABILITY_PAYLOAD_JSON."
        )
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def output_dir(cli_out=None) -> Path:
    if cli_out:
        return Path(cli_out)
    base = os.environ.get("REPORT_PATH")
    if base:
        return Path(base) / "deliverability"
    return Path.cwd() / "output" / "deliverability"


def template_docx() -> str:
    return str(Path(__file__).parent / "assets" / "template.docx")


def runner_command() -> str:
    base = os.environ.get("RUNNER_PATH", DEFAULT_RUNNER_PATH)
    return f"{base}/generate_scheduled_report.sh"
