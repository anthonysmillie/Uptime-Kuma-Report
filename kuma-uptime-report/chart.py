import pandas as pd
import plotly.express as px
from datetime import datetime
from typing import Optional
from .database import Database


def chart_plotly(
        start: datetime,
        end: datetime,
        tagname: Optional[str] = None,
        caption: Optional[str] = None
):
    """Returns a Plotly chart for the given timespan."""
    db = Database.db
    cur = db.cursor()

    # Query monitors based on tagname
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
        raise ValueError("No active monitors found for the given tag or query.")

    # Prepare data
    report_data = []
    for mon_id, mon_name in monitors:
        uptime = db.percent_by_monitor_id(mon_id, start, end)
        report_data.append({"Id": mon_id, "Name": mon_name, "Uptime": uptime})

    # Create dataframe and plot
    df = pd.DataFrame(report_data)
    if df.empty:
        raise ValueError("No uptime data available for the selected period.")

    return px.bar(df, x="Name", y="Uptime", title=caption, hover_data=["Uptime"])