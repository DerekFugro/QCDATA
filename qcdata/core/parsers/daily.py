"""Daily_ARAN01_<day>.csv - the crew's list of the day's runs.

Row 1 is the header; row 2 is a blank spacer. Run rows start with a bracketed
run id; a '[0]' row is a section with no run; footer rows (ACS version, report
version, time in motion) are metadata. Columns are read by header name.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from qcdata.core.model import DailyFile, DailyRow, RunId, Skipped
from qcdata.core.parsers._util import log, to_float

_FOOTER = (
    (re.compile(r"^ACS Version\s+(.+)$", re.I), "acs_version"),
    (re.compile(r"^Daily Report Version\s+(.+)$", re.I), "report_version"),
    (re.compile(r"^Time in motion\s*-\s*(.+)$", re.I), "time_in_motion"),
)


def comment_kind(comment: str) -> str:
    """'collected_short' if the crew wrote 'Section Collected Short' anywhere in the
    comment (it is often appended after an 'Other - ...' note), else 'delete',
    'other', or '' for no comment."""
    c = comment.strip().lower()
    if not c:
        return ""
    if "section collected short" in c:
        return "collected_short"
    if c.startswith("delete file"):
        return "delete"
    return "other"


def parse_daily(path: Path, day: str) -> DailyFile:
    path = Path(path)
    out = DailyFile(path=path, day=day)
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header is None:
            out.skipped.append(Skipped(path, 1, "empty file"))
            return out
        col = {name.strip(): i for i, name in enumerate(header) if name.strip()}

        for line_no, cells in enumerate(reader, start=2):
            if not any(c.strip() for c in cells):
                continue
            def get(name: str) -> str:
                i = col.get(name)
                return cells[i].strip() if i is not None and i < len(cells) else ""
            first = cells[0].strip()
            if not first and any(c.strip().lower() == "averages:" for c in cells):
                out.meta["has_averages_row"] = "yes"   # the Daily's summary line
                continue
            run = RunId.parse(first)
            if run is None and first != "[0]":
                for pattern, key in _FOOTER:
                    m = pattern.match(first)
                    if m:
                        out.meta[key] = m.group(1).strip()
                        break
                else:
                    out.skipped.append(Skipped(path, line_no, f"unrecognised row: {first[:40]!r}"))
                    log.debug("skip %s:%d", path, line_no)
                continue
            comment = get("Comments")
            out.rows.append(DailyRow(
                run=run, raw_filename=first, section=get("HEADER"),
                status=get("Status").upper(), comment=comment, comment_kind=comment_kind(comment),
                initials=get("Initials"), length_km=to_float(get("Length")),
                collected_length_km=to_float(get("CollLength")), gps_mode=get("GPS Mode"),
                lat_beg=to_float(get("LatBeg")), long_beg=to_float(get("LongBeg")),
                date_text=get("Date"), line_no=line_no,
            ))
    return out
