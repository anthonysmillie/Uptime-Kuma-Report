"""Static report recipe: dashboards, panel->slot mapping, layouts, validation config.

This is the ONLY file that needs editing if the Grafana dashboards change (panel IDs
renamed/rebuilt, a section gains/loses a panel) or the .docx template's image slots
change. Everything else is generic. Keep it in sync with the two dashboards.
"""

# Grafana dashboards the report draws from (folder "Delivery", need org-Admin on the SA token).
DASHBOARDS = {
    "A": {"uid": "fd86b0fc-564d-4718-a0d9-1f2a4272147f", "slug": "email-delivery-metrics-overview"},
    "B": {"uid": "ee75b3dc-704c-4492-818d-7d822a5f0ce0", "slug": "gmail-smtp-error-monitoring-dashboard"},
}

# Each SLOT maps one template image (word/media/imageN.png) to one or more Grafana panels.
#   layout "single"  -> one panel, dropped in as-is.
#   layout "row"     -> panels stitched left-to-right, scaled to a common height (row_h;
#                       None means use the first panel's native height).
#   layout "grid2x2" -> four panels stitched into a 2x2 grid.
# Per-panel: dash (A/B), id (Grafana panel id), vw/vh (render viewport px), and optional
# flags: stat (wait for the big value to paint) and capture (tag the parsed value).
SLOTS = [
    {"media": "image2.png", "layout": "row", "row_h": 360, "panels": [
        {"dash": "A", "id": 92, "vw": 340, "vh": 200, "stat": True, "capture": "delivered"},
        {"dash": "A", "id": 95, "vw": 340, "vh": 200, "stat": True},
        {"dash": "A", "id": 94, "vw": 340, "vh": 200, "stat": True},
        {"dash": "A", "id": 105, "vw": 600, "vh": 180},
    ]},
    {"media": "image3.png", "layout": "single", "panels": [
        {"dash": "A", "id": 103, "vw": 1300, "vh": 194}]},
    {"media": "image4.png", "layout": "single", "panels": [
        {"dash": "A", "id": 24, "vw": 1300, "vh": 238}]},
    {"media": "image5.png", "layout": "grid2x2", "panels": [
        {"dash": "A", "id": 46, "vw": 700, "vh": 330},
        {"dash": "A", "id": 101, "vw": 700, "vh": 330},
        {"dash": "A", "id": 27, "vw": 700, "vh": 330},
        {"dash": "A", "id": 100, "vw": 700, "vh": 330}]},
    {"media": "image6.png", "layout": "single", "panels": [
        {"dash": "A", "id": 107, "vw": 720, "vh": 394}]},
    {"media": "image7.png", "layout": "single", "panels": [
        {"dash": "A", "id": 48, "vw": 720, "vh": 395}]},
    {"media": "image8.png", "layout": "row", "row_h": None, "panels": [
        {"dash": "A", "id": 72, "vw": 680, "vh": 170},
        {"dash": "A", "id": 98, "vw": 680, "vh": 170}]},
    {"media": "image9.png", "layout": "single", "panels": [
        {"dash": "B", "id": 29, "vw": 900, "vh": 363}]},
    {"media": "image10.png", "layout": "grid2x2", "panels": [
        {"dash": "B", "id": 26, "vw": 720, "vh": 330},
        {"dash": "B", "id": 46, "vw": 720, "vh": 330},
        {"dash": "B", "id": 44, "vw": 720, "vh": 330},
        {"dash": "B", "id": 78, "vw": 720, "vh": 330}]},
]

# Text baked into the pristine template (assets/template.docx). The builder finds these
# exact strings (some char-split across runs) and rewrites them. The two dates are stamped
# with the report's RUN/generation date (not the reporting week). If you swap the template,
# update these to match its baked-in values.
TEMPLATE_TITLE_DATE = "15-07-2026"          # appears twice (title page) -> run date
TEMPLATE_VERSION_DATE = "12/05/2026"        # version-control "Date of Update" -> run date
TEMPLATE_EDITOR = "Anthony Smillie"         # version-control "Last Edited by"
EDITOR_REPLACEMENT = "Report Automation"    # generic automated-author label

# Cover + header/footer logos — never touched.
PROTECTED_MEDIA = {"image1.png", "image11.png", "image12.emf", "image13.png"}

# Delivery-volume sanity band (skippable check). Total Delivered Mails for a normal week
# sits ~44-50M; anything outside this band means an MTA likely stopped shipping logs.
DELIVERY_CHECK = {
    "capture": "delivered",
    "low": 40_000_000,
    "high": 60_000_000,
    "label": "Total Delivered Mails",
}


def all_required_panels():
    """-> list of (dash_key, panel_id) every render depends on (for existence validation)."""
    out = []
    for slot in SLOTS:
        for p in slot["panels"]:
            out.append((p["dash"], p["id"]))
    return out


def render_jobs():
    """Flatten SLOTS into render jobs. Each -> (dash, id, vw, vh, stat, capture, outfile).

    outfile is a per-panel temp name: '<media-stem>__<index>.png'.
    """
    jobs = []
    for slot in SLOTS:
        stem = slot["media"].rsplit(".", 1)[0]
        for i, p in enumerate(slot["panels"]):
            jobs.append({
                "dash": p["dash"], "id": p["id"], "vw": p["vw"], "vh": p["vh"],
                "stat": p.get("stat", False), "capture": p.get("capture"),
                "outfile": f"{stem}__{i}.png",
            })
    return jobs
