"""Render the report data (core.report_data) to one self-contained HTML page.

Jinja2 autoescaping is ON: filenames, comments and log messages come from the
van and are untrusted, so they must render as text, never as markup.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES = Path(__file__).parent / "templates"

_ICON = {"PASS": "✓", "WARN": "!", "FAIL": "✕"}


def plain_date(day: str) -> str:
    try:
        d = datetime.strptime(day, "%Y%m%d")
    except ValueError:
        return day
    return f"{d:%A}, {d:%B} {d.day}, {d.year}"


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True,
                      undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
    env.filters["plain_date"] = plain_date
    env.globals["icon"] = lambda v: _ICON.get(v, "")
    return env


def render_html(data: dict[str, Any], csv_name: str | None, json_name: str | None) -> str:
    return _env().get_template("report.html.j2").render(r=data, csv_name=csv_name, json_name=json_name)
