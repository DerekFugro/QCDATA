"""Everything the HTML report, the JSON file, and the CLI render from - as plain,
deterministically ordered data. Two runs on unchanged data give identical output
apart from `generated_at`."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from qcdata import __version__
from qcdata.core.checks.base import cap, rd_label
from qcdata.core.parsers.daily import comment_kind
from qcdata.core.engine import CheckRun, by_section
from qcdata.core.model import Finding

VERDICT_WORDS = {"PASS": "PASS", "WARN": "NEEDS A LOOK", "FAIL": "PROBLEM FOUND"}


def finding_dict(f: Finding) -> dict[str, Any]:
    return {
        "check": f.check_id, "severity": f.severity.value, "section": f.section, "day": f.day,
        "run": str(f.run) if f.run else None, "subject": f.subject, "message": f.message_plain,
        "technical": f.message_technical, "what_to_do": f.what_to_do,
        "details": {k: v for k, v in sorted(f.details.items())},
    }


def status_words(row) -> str:
    if row.status == "C" and comment_kind(row.comment) == "collected_short":
        return "Collected short"
    return {"C": "Collected", "V": "Verification", "X": "Deleted"}.get(row.status, row.status)


def images_rows(r) -> list[dict[str, Any]]:
    """Photo counts per checked run - never the per-photo list (that is the CSV)."""
    out = []
    for run in sorted(r.data.runs):
        rd = r.data.runs[run]
        if not (rd.daily and rd.daily.is_checked):
            continue
        counts = {v: (seq.count if seq else None) for v, seq in sorted(rd.photos.items())}
        out.append({"run": str(run), "label": cap(rd_label(rd)),
                    "row": counts.get("ROW"), "rear": counts.get("Rear"),
                    "expected": len(rd.pulse_plan.photo_pulses_us) + 1 if rd.pulse_plan else None})
    return out


def plain_day(day: str) -> str:
    try:
        d = datetime.strptime(day, "%Y%m%d")
    except ValueError:
        return day
    return f"{d:%a} {d:%b} {d.day}"


def target_name(target) -> str:
    """What the crew calls the place they checked: 'F:\\' or the folder name."""
    p = Path(target)
    return str(p) if p.anchor and str(p) == p.anchor else (p.name or str(p))


def build(result: CheckRun, generated_at: datetime | None = None) -> dict[str, Any]:
    days = []
    for day in sorted(result.days):
        r = result.days[day]
        sections = by_section(r)
        todo: list[str] = []
        for f in sections["crew"]:
            if f.what_to_do and f.what_to_do not in todo:
                todo.append(f.what_to_do)
        daily_rows = []
        if r.data.daily:
            for row in r.data.daily.rows:
                daily_rows.append({
                    "run": str(row.run) if row.run else row.raw_filename,
                    "status": row.status,
                    "status_words": status_words(row),
                    "section": row.section, "length_km": row.length_km,
                    "collected_length_km": row.collected_length_km, "comment": row.comment,
                    "initials": row.initials,
                })
        days.append({
            "day": day, "verdict": r.verdict.value, "verdict_words": VERDICT_WORDS[r.verdict.value],
            "stats": r.stats, "what_to_do": todo,
            "findings": [finding_dict(f) for f in sections["crew"]],
            "explained": [finding_dict(f) for f in sections["explained"]],
            "technical": [finding_dict(f) for f in sections["technical"]],
            "daily": daily_rows,
            "images": images_rows(r),
        })
    when = generated_at or datetime.now()
    many = len(days) > 1
    overall_todo: list[str] = []
    for d in days:
        for item in d["what_to_do"]:
            line = f"{plain_day(d['day'])}: {item}" if many else item
            if line not in overall_todo:
                overall_todo.append(line)
    return {
        "app": "QCDATA", "version": __version__,
        "generated_at": when.isoformat(timespec="seconds"),
        "checked_at_words": f"{when:%B} {when.day}, {when.year} at {when:%I:%M %p}".replace(" 0", " "),
        "target": str(result.target), "target_name": target_name(result.target),
        "overall_verdict": result.verdict.value, "what_to_do": overall_todo,
        "overall_verdict_words": VERDICT_WORDS[result.verdict.value],
        "days": days,
    }
