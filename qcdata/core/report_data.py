"""Everything the HTML report, the JSON file, and the CLI render from - as plain,
deterministically ordered data. Two runs on unchanged data give identical output
apart from `generated_at`."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from qcdata import __version__
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
                    "status_words": {"C": "Collected", "V": "Verification", "X": "Deleted"}.get(row.status, row.status),
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
        })
    return {
        "app": "QCDATA", "version": __version__,
        "generated_at": (generated_at or datetime.now()).isoformat(timespec="seconds"),
        "target": str(result.target), "overall_verdict": result.verdict.value,
        "overall_verdict_words": VERDICT_WORDS[result.verdict.value],
        "days": days,
    }
