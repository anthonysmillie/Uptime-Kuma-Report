"""Multi-section report assembly: interactive HTML (Plotly) and static HTML (matplotlib)."""
from datetime import datetime
from html import escape
from typing import List, Optional

from .chart import chart_matplotlib_png_data_uri, chart_plotly, fetch_report_data


class ReportSection:
    def __init__(self, name: str, tag: Optional[str]):
        self.name = name
        self.tag = tag

    @classmethod
    def from_dict(cls, d: dict) -> "ReportSection":
        return cls(name=d["name"], tag=d.get("tag"))


def _decorate_header(name: str, days: Optional[int], start: datetime, end: datetime) -> str:
    if days is not None:
        return f"{name} - {days} Days - {start.strftime('%d-%m-%Y')} to {end.strftime('%d-%m-%Y')}"
    return f"{name} - {start.strftime('%d-%m-%Y')} to {end.strftime('%d-%m-%Y')}"


def _decorate_section(name: str, days: Optional[int]) -> str:
    if days is not None:
        return f"{name} - {days} Days"
    return name


def _section_captions(
    header: ReportSection,
    sections: List[ReportSection],
    days: Optional[int],
    start: datetime,
    end: datetime,
) -> List[tuple]:
    """Pair sections (header + remaining) with their decorated captions in display order."""
    title = _decorate_header(header.name, days, start, end)
    out = [(header, title)]
    for section in sections:
        out.append((section, _decorate_section(section.name, days)))
    return out


def build_interactive_html(
    header: ReportSection,
    sections: List[ReportSection],
    start: datetime,
    end: datetime,
    days: Optional[int],
    min_y: int,
) -> str:
    """Stitch one HTML doc containing N interactive Plotly charts with a single Plotly.js load."""
    captioned = _section_captions(header, sections, days, start, end)
    title = captioned[0][1]

    fragments = []
    for idx, (section, caption) in enumerate(captioned):
        fig = chart_plotly(start=start, end=end, tagname=section.tag, caption=caption, min_y=min_y)
        include_js = "cdn" if idx == 0 else False
        fragment = fig.to_html(include_plotlyjs=include_js, full_html=False)
        fragments.append(
            f'<section class="kuma-section">\n'
            f'<h2>{escape(section.name)}</h2>\n'
            f'{fragment}\n'
            f'</section>'
        )

    body = "\n".join(fragments)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(title)}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; }}
  h1 {{ margin-bottom: 24px; }}
  .kuma-section {{ margin-bottom: 36px; }}
  .kuma-section h2 {{ margin: 0 0 8px 0; }}
</style>
</head>
<body>
<h1>{escape(title)}</h1>
{body}
</body>
</html>
"""


def build_static_html(
    header: ReportSection,
    sections: List[ReportSection],
    start: datetime,
    end: datetime,
    days: Optional[int],
    min_y: int,
) -> str:
    """Build a print-friendly HTML doc with matplotlib PNG charts (for WeasyPrint PDF)."""
    captioned = _section_captions(header, sections, days, start, end)
    title = captioned[0][1]

    blocks = []
    for idx, (section, caption) in enumerate(captioned):
        data = fetch_report_data(start, end, section.tag)
        png_uri = chart_matplotlib_png_data_uri(data, caption=caption, min_y=min_y)
        page_break = "" if idx == 0 else 'style="page-break-before: always;"'
        blocks.append(
            f'<section class="kuma-section" {page_break}>\n'
            f'<h2>{escape(section.name)}</h2>\n'
            f'<img src="{png_uri}" alt="{escape(section.name)}">\n'
            f'</section>'
        )

    body = "\n".join(blocks)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(title)}</title>
<style>
  @page {{ size: A4 landscape; margin: 18mm; }}
  body {{ font-family: "Helvetica", "Arial", sans-serif; }}
  h1 {{ font-size: 18pt; margin-bottom: 18pt; }}
  h2 {{ font-size: 13pt; margin: 0 0 6pt 0; }}
  .kuma-section img {{ width: 100%; height: auto; }}
</style>
</head>
<body>
<h1>{escape(title)}</h1>
{body}
</body>
</html>
"""


def render_pdf(static_html: str, pdf_path: str) -> None:
    """Convert static HTML to PDF via WeasyPrint."""
    from weasyprint import HTML
    HTML(string=static_html).write_pdf(pdf_path)
