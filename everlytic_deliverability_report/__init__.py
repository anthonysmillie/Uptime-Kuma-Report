"""Everlytic Weekly Deliverability Report.

Generates the weekly Everlytic "Infrastructure Update" Word document by rendering
Grafana panels for the previous calendar week (SAST) into a fixed .docx template,
validates the result, and emails it via the shared Uptime-Kuma email API.

Deliberately self-contained (stdlib zipfile + lxml + Pillow + playwright); it does
NOT depend on the Claude office-skills plugin. See CLAUDE.md at the repo root.
"""
__version__ = "1.0.0"
