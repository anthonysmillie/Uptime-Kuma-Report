"""POST a generated report to an external email API using basic auth."""
import base64
import copy
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

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
    attachment_paths: Union[str, List[str]],
    days: Optional[int],
    start: datetime,
    end: datetime,
) -> dict:
    payload = copy.deepcopy(template)

    headers = payload.setdefault("headers", {})
    subject = headers.get("subject", "")
    headers["subject"] = f"{subject}{_date_range_suffix(days, start, end)}"

    if isinstance(attachment_paths, str):
        attachment_paths = [attachment_paths]

    attachments = payload.setdefault("attachments", {})
    data_list = []
    for attachment_path in attachment_paths:
        path = Path(attachment_path)
        with path.open("rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        data_list.append({"filename": path.name, "data": encoded})
    attachments["data"] = data_list

    return payload


def send(payload: dict, timeout: int = 30) -> requests.Response:
    endpoint, username, password = api_credentials()
    response = requests.post(
        endpoint,
        json=payload,
        auth=HTTPBasicAuth(username, password),
        timeout=timeout,
    )
    sys.stderr.write(
        f"Email API response: {response.status_code} {response.reason}\n"
        f"Body: {response.text}\n"
    )
    if not response.ok:
        response.raise_for_status()
    return response
