import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

REPORT_FILENAME = "report_config.json"
PAYLOAD_FILENAME = "payload_config.json"


def load_env() -> None:
    load_dotenv(Path.cwd() / ".env")


def _resolve_path(cli_path: Optional[str], env_var: str, default_filename: str) -> Optional[Path]:
    if cli_path:
        return Path(cli_path)
    env_path = os.environ.get(env_var)
    if env_path:
        return Path(env_path)
    cwd_path = Path.cwd() / default_filename
    if cwd_path.exists():
        return cwd_path
    return None


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_report_config(cli_path: Optional[str]) -> Optional[dict]:
    path = _resolve_path(cli_path, "REPORT_JSON", REPORT_FILENAME)
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"Report config not found at {path}")
    return _load_json(path)


def load_payload_config(cli_path: Optional[str]) -> dict:
    path = _resolve_path(cli_path, "PAYLOAD_JSON", PAYLOAD_FILENAME)
    if path is None:
        raise FileNotFoundError(
            f"Payload config not found. Pass --payload, set PAYLOAD_JSON, "
            f"or place {PAYLOAD_FILENAME} in the working directory."
        )
    if not path.exists():
        raise FileNotFoundError(f"Payload config not found at {path}")
    return _load_json(path)


def api_credentials() -> tuple[str, str, str]:
    endpoint = os.environ.get("API_ENDPOINT")
    username = os.environ.get("API_USERNAME")
    password = os.environ.get("API_PASSWORD")
    missing = [k for k, v in {"API_ENDPOINT": endpoint, "API_USERNAME": username, "API_PASSWORD": password}.items() if not v]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
    return endpoint, username, password


def report_path() -> Optional[Path]:
    value = os.environ.get("REPORT_PATH")
    return Path(value) if value else None
