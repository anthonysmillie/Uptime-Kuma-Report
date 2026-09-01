"""Reporting-window date maths, always resolved in SAST regardless of server TZ."""
from datetime import datetime, timedelta
from typing import NamedTuple, Optional

import pytz

SAST = pytz.timezone("Africa/Johannesburg")


class Window(NamedTuple):
    start: datetime          # tz-aware SAST, Mon 00:00:00
    end: datetime            # tz-aware SAST, Sun 23:59:59.999999
    from_ms: int             # epoch millis for Grafana `from`
    to_ms: int               # epoch millis for Grafana `to`
    stamp_title: str         # "dd-mm-yyyy" (week-end Sunday) for the docx title page
    stamp_version: str       # "dd/mm/yyyy" for the version-control table
    subject_range: str       # "dd/mm/yyyy-dd/mm/yyyy" for the email subject


def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def previous_week(now: Optional[datetime] = None) -> Window:
    """Previous full calendar week in SAST: Mon 00:00:00 -> Sun 23:59:59.999999."""
    if now is None:
        now = datetime.now(SAST)
    elif now.tzinfo is None:
        now = SAST.localize(now)
    now = now.astimezone(SAST)

    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    this_monday = midnight - timedelta(days=now.weekday())
    start = this_monday - timedelta(days=7)
    end = this_monday - timedelta(microseconds=1)
    return _build(start, end)


def explicit_week(start_date: str, end_date: str) -> Window:
    """Manual override. start_date/end_date as 'YYYY-MM-DD' (inclusive), interpreted in SAST."""
    s = SAST.localize(datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0))
    e = SAST.localize(datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999))
    if s >= e:
        raise ValueError("start date must be before end date")
    return _build(s, e)


def _build(start: datetime, end: datetime) -> Window:
    return Window(
        start=start,
        end=end,
        from_ms=_to_ms(start),
        to_ms=_to_ms(end),
        stamp_title=end.strftime("%d-%m-%Y"),
        stamp_version=end.strftime("%d/%m/%Y"),
        subject_range=f"{start.strftime('%d/%m/%Y')}-{end.strftime('%d/%m/%Y')}",
    )
