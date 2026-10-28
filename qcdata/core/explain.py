"""The explained-by-the-crew rule.

Runs the Daily marks X are not checked; they are listed with the crew's comment.
A run whose comment contains 'Section Collected Short' has its short-tail (C6)
findings moved to "Explained by the crew". Explained findings stay visible and
never raise the verdict - never warn about something the crew already explained.
"""

from __future__ import annotations

from dataclasses import replace

from qcdata.core.checks.base import cap, run_label
from qcdata.core.loader import DayData
from qcdata.core.model import CREW, EXPLAINED, Finding, Severity


def apply(day: DayData, findings: list[Finding]) -> list[Finding]:
    out: list[Finding] = []
    short_runs = {rd.run: rd.daily.comment for rd in day.runs.values()
                  if rd.daily and rd.daily.is_checked and rd.daily.comment_kind == "collected_short"}
    delete_noted = {rd.run: rd.daily.comment for rd in day.runs.values()
                    if rd.daily and rd.daily.is_checked and rd.daily.comment_kind == "delete"}
    for f in findings:
        if f.section == CREW and f.run in delete_noted:
            f = replace(f, message_plain=f"{f.message_plain} The crew wrote \u201c{delete_noted[f.run]}\u201d "
                                      f"but the Daily still marks this run as collected.",
                        what_to_do="Check whether this run should have been marked deleted (X) in the Daily.")
        if f.section == CREW and f.check_id == "C6" and f.run in short_runs:
            out.append(replace(f, severity=Severity.PASS, section=EXPLAINED,
                               message_plain=f"{f.message_plain} The crew noted: “{short_runs[f.run]}”",
                               what_to_do=""))
        else:
            out.append(f)
    if day.daily:
        for row in day.daily.run_rows:
            if row.status == "X":
                comment = f" — “{row.comment}”" if row.comment else ""
                out.append(Finding("Daily", Severity.PASS, EXPLAINED, day.day, row.run, "",
                                   f"{cap(run_label(row.run))} was deleted by the crew{comment}.",
                                   f"{row.run}: Daily status X; not checked.", "",
                                   {"status": "X", "comment": row.comment}))
            elif row.status not in ("C", "V"):
                out.append(Finding("Daily", Severity.PASS, "technical", day.day, row.run, "",
                                   f"{cap(run_label(row.run))} has an unknown Daily status "
                                   f"“{row.status}”, so it wasn't checked.",
                                   f"{row.run}: Daily status {row.status!r}.", "", {}))
    return out
