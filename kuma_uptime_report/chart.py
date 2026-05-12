import io
from datetime import datetime
from typing import List, Optional

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px

from .database import Database


def fetch_report_data(
        start: datetime,
        end: datetime,
        tagname: Optional[str] = None,
) -> List[dict]:
    """Return [{Id, Name, Uptime}, ...] for active monitors matching `tagname` (or all)."""
    db = Database.db
    cur = db.cursor()

    if not tagname:
        cur.execute("SELECT monitor.id, monitor.name FROM monitor WHERE monitor.active = 1")
    else:
        cur.execute("""
            SELECT monitor.id, monitor.name
            FROM monitor
            JOIN monitor_tag ON monitor.id = monitor_tag.monitor_id
            JOIN tag ON tag.id = monitor_tag.tag_id
            WHERE tag.name = ? AND monitor.active = 1
        """, (tagname,))

    monitors = cur.fetchall()
    if not monitors:
        raise ValueError(f"No active monitors found for tag {tagname!r}." if tagname
                         else "No active monitors found.")

    report_data = []
    for mon_id, mon_name in monitors:
        uptime = db.percent_by_monitor_id(mon_id, start, end)
        report_data.append({"Id": mon_id, "Name": mon_name, "Uptime": uptime})
    return report_data


def chart_plotly(
        start: datetime,
        end: datetime,
        tagname: Optional[str] = None,
        caption: Optional[str] = None,
        min_y: int = 0,
):
    """Plotly bar chart figure for the given timespan."""
    report_data = fetch_report_data(start, end, tagname)
    df = pd.DataFrame(report_data)
    if df.empty:
        raise ValueError("No uptime data available for the selected period.")
    fig = px.bar(df, x="Name", y="Uptime", title=caption, hover_data=["Uptime"])
    fig.update_layout(yaxis=dict(range=[min_y, 100]))
    return fig


def chart_matplotlib_svg(
        report_data: List[dict],
        caption: Optional[str] = None,
        min_y: int = 0,
) -> str:
    """Render a static bar chart as inline SVG markup for embedding in HTML."""
    if not report_data:
        raise ValueError("No uptime data available for the selected period.")

    names = [row["Name"] for row in report_data]
    uptimes = [row["Uptime"] for row in report_data]

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.bar(names, uptimes, color="#1f77b4")
    ax.set_ylim(min_y, 100)
    ax.set_ylabel("Uptime (%)")
    if caption:
        ax.set_title(caption)
    ax.tick_params(axis="x", labelrotation=45)
    for label in ax.get_xticklabels():
        label.set_horizontalalignment("right")
    fig.tight_layout()

    buf = io.StringIO()
    fig.savefig(buf, format="svg")
    plt.close(fig)
    svg = buf.getvalue()
    start_idx = svg.find("<svg")
    return svg[start_idx:] if start_idx != -1 else svg
