"""POST a generated report to an external email API using basic auth."""
import base64
import copy
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth

from .config import api_credentials


def _date_range_suffix(days: Optional[int], start: datetime, end: datetime) -> str:
    start_str = start.strftime("%d/%m/%Y")
    end_str = end.strftime("%d/%m/%Y")
    if days is not None:
        return f" - {days} Days - {start_str}-{end_str}"
    return f" - {start_str}-{end_str}"


def build_payload(
    template: dict,
    attachment_path: str,
    days: Optional[int],
    start: datetime,
    end: datetime,
) -> dict:
    payload = copy.deepcopy(template)

    headers = payload.setdefault("headers", {})
    subject = headers.get("subject", "")
    headers["subject"] = f"{subject}{_date_range_suffix(days, start, end)}"

    path = Path(attachment_path)
    with path.open("rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")

    attachments = payload.setdefault("attachments", {})
    data_list = attachments.setdefault("data", [])
    if not data_list:
        data_list.append({})
    data_list[0]["filename"] = path.name
    data_list[0]["data"] = encoded

    return payload


def send(payload: dict, timeout: int = 30) -> requests.Response:
    endpoint, username, password = api_credentials()
    response = requests.post(
        endpoint,
        json=payload,
        auth=HTTPBasicAuth(username, password),
        timeout=timeout,
    )
    if not response.ok:
        sys.stderr.write(
            f"Email API POST failed: {response.status_code} {response.reason}\n"
            f"Body: {response.text}\n"
        )
        response.raise_for_status()
    return response
