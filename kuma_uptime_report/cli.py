import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

import click

from .config import load_env, load_payload_config, load_report_config
from .database import Database
from .email_send import build_payload, send
from .output import build_filename, resolve_dirs, unique_path
from .report import (
    ReportSection,
    build_interactive_html,
    build_static_html,
    render_pdf,
)


def _resolve_date_range(
    start: Optional[str], end: Optional[str], days: Optional[int]
) -> Tuple[datetime, datetime, int]:
    """Return (start_dt, end_dt, days_label) — days_label feeds filename/title decoration."""
    if start and end:
        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = datetime.strptime(end, "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            raise click.UsageError("Invalid date format. Use yyyy-mm-dd for --start and --end.")
        if start_dt >= end_dt:
            raise click.UsageError("Start date must be before end date.")
        return start_dt, end_dt, max((end_dt - start_dt).days, 1)
    if days:
        if days <= 0:
            raise click.UsageError("Number of days must be greater than zero.")
        end_dt = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        start_dt = end_dt - timedelta(days=days)
        return start_dt, end_dt, days
    raise click.UsageError("You must provide either --start and --end or --days.")


def _resolve_sections(
    caption: Optional[str],
    tag: Optional[str],
    report_config_path: Optional[str],
    min_y_cli: Optional[int],
) -> Tuple[ReportSection, List[ReportSection], int]:
    if caption and tag:
        return ReportSection(name=caption, tag=tag), [], (min_y_cli or 0)

    config = load_report_config(report_config_path)
    if config is None:
        raise click.UsageError(
            "No report_config.json found. Pass --config, set $REPORT_JSON, place the file in CWD, "
            "or use -c and -t together for single-section mode."
        )

    try:
        header = ReportSection.from_dict(config["header"])
    except KeyError:
        raise click.UsageError("report_config.json missing required 'header' object.")
    sections = [ReportSection.from_dict(s) for s in config.get("sections", [])]

    config_min_y = config.get("global_settings", {}).get("min_y", 0)
    min_y = min_y_cli if min_y_cli is not None else config_min_y
    return header, sections, min_y


@click.command(help="""
Generate an Uptime Kuma uptime report.

Modes:
  Single section: pass BOTH -c/--caption and -t/--tag (skips report_config.json).
  Multi-section:  pass NEITHER. Reads report_config.json (via --config, $REPORT_JSON, or CWD).

Output:
  HTML is always written. Pass --pdf to also write a PDF (no email). Pass --send-email
  to write the PDF and POST it to $API_ENDPOINT with basic auth.

Output location:
  -o/--output DIR overrides everything (both files dropped into DIR).
  Otherwise $REPORT_PATH from .env is used: HTML goes to $REPORT_PATH/html,
  PDF goes to $REPORT_PATH/pdf. Filenames are
  UptimeKumaReport_<days>-Days_<dd-mm-yyyy>.<ext> with _2, _3, ... appended on collision.
""")
@click.option('--caption', '-c', type=str, default=None,
              help='Chart title (single-section mode). Must be used together with -t.')
@click.option('--tag', '-t', type=str, default=None,
              help='Monitor tag (single-section mode). Must be used together with -c.')
@click.option('--db', type=click.Path(exists=True), required=True,
              help='Path to the Uptime Kuma SQLite database.')
@click.option('--start', type=str, help='Start date in the format yyyy-mm-dd.')
@click.option('--end', type=str, help='End date in the format yyyy-mm-dd.')
@click.option('--days', '-d', type=int,
              help='Number of days to include in the report (if --start/--end are not provided).')
@click.option('--min-y', 'min_y', type=int, default=None,
              help='Minimum y-axis value for charts (overrides config).')
@click.option('--config', '--report-config', 'report_config_path', type=click.Path(),
              help='Path to report_config.json. Overrides $REPORT_JSON.')
@click.option('--payload', '--payload-config', 'payload_config_path', type=click.Path(),
              help='Path to payload_config.json. Overrides $PAYLOAD_JSON.')
@click.option('--output', '-o', 'output_dir', type=click.Path(file_okay=False),
              help='Output directory for HTML (and PDF, if --pdf/--send-email). '
                   'Overrides $REPORT_PATH from .env.')
@click.option('--pdf', 'pdf_flag', is_flag=True, default=False,
              help='Also render a PDF copy alongside the HTML. No email is sent.')
@click.option('--send-email', is_flag=True, default=False,
              help='Render a PDF and POST it to the configured email API.')
def cli(
    db: str,
    start: Optional[str],
    end: Optional[str],
    days: Optional[int],
    tag: Optional[str],
    caption: Optional[str],
    min_y: Optional[int],
    report_config_path: Optional[str],
    payload_config_path: Optional[str],
    output_dir: Optional[str],
    pdf_flag: bool,
    send_email: bool,
):
    load_env()

    if (caption is None) ^ (tag is None):
        raise click.UsageError(
            "--caption/-c and --tag/-t must be passed together; "
            "pass both for single-section mode, neither to use report_config.json."
        )

    start_date, end_date, days_label = _resolve_date_range(start, end, days)

    try:
        html_dir, pdf_dir = resolve_dirs(output_dir)
    except RuntimeError as e:
        raise click.UsageError(str(e))

    try:
        Database(db)
    except RuntimeError as e:
        click.echo(f"Error connecting to database: {e}", err=True)
        sys.exit(1)

    try:
        header, sections, effective_min_y = _resolve_sections(
            caption, tag, report_config_path, min_y
        )

        gen_date = datetime.now()
        html_filename = build_filename(days_label, gen_date, "html")
        html_path = unique_path(html_dir, html_filename)

        interactive_html = build_interactive_html(
            header=header, sections=sections,
            start=start_date, end=end_date, days=days_label, min_y=effective_min_y,
        )
        html_path.write_text(interactive_html, encoding="utf-8")
        click.echo(f"HTML written to {html_path}", err=True)

        want_pdf = pdf_flag or send_email
        pdf_path: Optional[Path] = None
        if want_pdf:
            static_html = build_static_html(
                header=header, sections=sections,
                start=start_date, end=end_date, days=days_label, min_y=effective_min_y,
            )
            pdf_filename = build_filename(days_label, gen_date, "pdf")
            pdf_path = unique_path(pdf_dir, pdf_filename)
            render_pdf(static_html, str(pdf_path))
            click.echo(f"PDF written to {pdf_path}", err=True)

        if send_email and pdf_path is not None:
            payload_template = load_payload_config(payload_config_path)
            payload = build_payload(payload_template, str(pdf_path), days_label, start_date, end_date)
            send(payload)
            click.echo(f"Report emailed; PDF attached as {pdf_path.name}.", err=True)

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
