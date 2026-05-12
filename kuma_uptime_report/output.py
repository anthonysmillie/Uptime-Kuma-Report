"""Output directory and filename resolution."""
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from .config import report_path


def resolve_dirs(output_dir_cli: Optional[str]) -> Tuple[Path, Path]:
    """
    Return (html_dir, pdf_dir).

    Precedence:
      - --output/-o (CLI):   both files go into the given directory.
      - $REPORT_PATH (env):  files split into <REPORT_PATH>/html and <REPORT_PATH>/pdf.
      - else:                raise — caller must surface a UsageError.
    """
    if output_dir_cli:
        base = Path(output_dir_cli)
        return base, base

    env_base = report_path()
    if env_base is not None:
        return env_base / "html", env_base / "pdf"

    raise RuntimeError(
        "No output location set. Pass --output/-o or set REPORT_PATH in your .env."
    )


def build_filename(days_label: int, gen_date: datetime, ext: str) -> str:
    """E.g. UptimeKumaReport_7-Days_12-05-2026.html"""
    return f"UptimeKumaReport_{days_label}-Days_{gen_date.strftime('%d-%m-%Y')}.{ext}"


def unique_path(directory: Path, filename: str) -> Path:
    """
    Return directory / filename, appending _2, _3, ... before the extension
    if a file with that name already exists.
    """
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / filename
    if not target.exists():
        return target

    stem, _, ext = filename.rpartition(".")
    counter = 2
    while True:
        candidate = directory / f"{stem}_{counter}.{ext}"
        if not candidate.exists():
            return candidate
        counter += 1
