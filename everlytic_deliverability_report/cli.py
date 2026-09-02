"""Orchestration + CLI for the Everlytic weekly deliverability report.

    python -m everlytic_deliverability_report --weekly --send-email
    python -m everlytic_deliverability_report --weekly --send-email --skip-delivery-validation
    python -m everlytic_deliverability_report --start 2026-08-24 --end 2026-08-30   # ad-hoc, no email

Flow: verify panels exist -> render -> verify renders -> delivery band check
(skippable) -> compose -> build docx -> verify -> email/save. Any ValidationFailure
sends a FAILED notification (when --send-email) and exits non-zero.
"""
import argparse
import html
import sys
import tempfile
import traceback

from . import config
from .dates import explicit_week, previous_week
from .panels import DASHBOARDS, DELIVERY_CHECK, all_required_panels, render_jobs
from .validate import ValidationFailure, check_delivery_band, check_panels_exist, check_renders_nonempty


def _log(msg: str) -> None:
    sys.stderr.write(f"[deliverability-report] {msg}\n")
    sys.stderr.flush()


def _parse_args(argv):
    p = argparse.ArgumentParser(prog="everlytic-deliverability-report",
                                description="Generate & email the Everlytic weekly deliverability report.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--weekly", action="store_true",
                   help="Previous calendar week, Mon 00:00 -> Sun 23:59:59 SAST (default).")
    p.add_argument("--start", help="Manual window start YYYY-MM-DD (use with --end; implies no --weekly).")
    p.add_argument("--end", help="Manual window end YYYY-MM-DD (inclusive).")
    p.add_argument("--send-email", action="store_true",
                   help="POST the report (or a FAILED notice) to the email API. Omit to just build locally.")
    p.add_argument("--skip-delivery-validation", action="store_true",
                   help="Skip ONLY the delivered-mail volume band check. Structural checks still run.")
    p.add_argument("--output", help="Output directory for the .docx (overrides REPORT_PATH).")
    p.add_argument("--payload", help="Path to the deliverability payload config JSON.")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    config.init_env()

    # resolve window
    if args.start or args.end:
        if not (args.start and args.end):
            _log("ERROR: --start and --end must be given together.")
            return 2
        window = explicit_week(args.start, args.end)
    else:
        window = previous_week()
    _log(f"window: {window.start.date()} -> {window.end.date()} (stamp {window.stamp_title})")

    try:
        url, token = config.grafana_creds()
    except RuntimeError as e:
        _log(f"ERROR: {e}")
        return 2

    # payload template needed for both success and failure emails
    template = None
    if args.send_email:
        try:
            template = config.load_payload_template(args.payload)
        except FileNotFoundError as e:
            _log(f"ERROR: {e}")
            return 2

    jobs = render_jobs()
    from . import render  # lazy: avoids importing playwright for --help / config errors

    with tempfile.TemporaryDirectory(prefix="evr-deliv-") as work:
        panels_dir = f"{work}/panels"
        final_dir = f"{work}/final"
        try:
            # 1) structural: every required panel still exists
            check_panels_exist(url, token, DASHBOARDS, all_required_panels())

            # 2) render all panels
            _log(f"rendering {len(jobs)} panels...")
            captured = render.render_all(url, token, window.from_ms, window.to_ms,
                                         panels_dir, jobs, DASHBOARDS)
            if "delivered" in captured:
                _log(f"delivered value read from Grafana: {captured['delivered']}")

            # 3) structural: no empty renders
            check_renders_nonempty(panels_dir, jobs)

            # 4) delivery band (skippable)
            if args.skip_delivery_validation:
                _log("delivery-volume validation SKIPPED (--skip-delivery-validation)")
            else:
                check_delivery_band(captured, DELIVERY_CHECK)

            # 5) compose + build docx
            from .compose import compose_all
            from . import docxbuild
            sizes = compose_all(panels_dir, final_dir)
            out_dir = config.output_dir(args.output)
            out_dir.mkdir(parents=True, exist_ok=True)
            # Filename keeps the reporting-week (Sunday) date; the in-doc stamps use the run date.
            out_path = str(out_dir / f"Everlytic Weekly Deliverability Report - {window.stamp_title}.docx")
            docxbuild.build(config.template_docx(), final_dir, sizes,
                            window.run_title, window.run_version, out_path)
            docxbuild.verify(out_path, window.run_title, sizes)
            _log(f"report built: {out_path}")

            # 6) email or leave on disk
            if args.send_email:
                emailer_send_success(template, out_path, window)
                _log("report emailed successfully.")
            else:
                _log("email skipped (--send-email not set).")
            return 0

        except ValidationFailure as f:
            _log(f"VALIDATION FAILED: {f.title} (skippable={f.skippable})")
            if args.send_email:
                from . import emailer
                emailer.send_failure(template, window, [f], config.runner_command())
                _log("FAILED notification email sent.")
            else:
                _log("email skipped (--send-email not set); not sending FAILED notice.")
            return 1

        except Exception as e:  # noqa: BLE001 - last-resort: never die silently
            _log(f"UNEXPECTED ERROR: {e}")
            _log(traceback.format_exc())
            if args.send_email:
                from . import emailer
                synthetic = ValidationFailure(
                    title="Report generation error",
                    detail_html=(
                        "<li>The report failed to generate due to an unexpected error: "
                        f"<code>{html.escape(str(e))}</code></li>"
                        "<li>This is most often a transient network or Grafana-availability "
                        "issue (each panel is already retried a few times before giving up). "
                        "Re-running usually resolves it; if it persists, confirm Grafana is "
                        "reachable from the host and check the log.</li>"
                    ),
                    skippable=False,
                )
                emailer.send_failure(template, window, [synthetic], config.runner_command())
                _log("FAILED notification email sent.")
            else:
                _log("email skipped (--send-email not set); not sending FAILED notice.")
            return 1


def emailer_send_success(template, out_path, window):
    from . import emailer
    emailer.send_success(template, out_path, window)


if __name__ == "__main__":
    raise SystemExit(main())
