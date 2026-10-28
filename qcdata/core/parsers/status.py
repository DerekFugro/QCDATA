"""ARAN01_StatusMessages_<day>.csv - every run started, plus warnings.

Header: FileName,Severity,Message,Module,StatusDate,DistanceStamp, (trailing
comma). Messages may contain commas, so the last three cells are taken from the
right and everything between Severity and Module is the message. Streamed.
"""

from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

from qcdata.core.model import RunId, Skipped, StatusMessage
from qcdata.core.parsers._util import log, to_float

_CODE = re.compile(r"^\s*(\d{3,6})\s*-\s")


def _time(text: str) -> datetime | None:
    try:
        return datetime.strptime(text.strip(), "%m/%d/%Y %I:%M:%S %p")
    except ValueError:
        return None


def parse_status_messages(path: Path) -> tuple[list[StatusMessage], list[Skipped]]:
    path = Path(path)
    msgs: list[StatusMessage] = []
    skipped: list[Skipped] = []
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        for line_no, line in enumerate(fh, start=1):
            if line_no == 1 or not line.strip():
                continue
            cells = next(csv.reader([line]))
            # Each row ends with one trailing comma; drop only that empty cell, so a
            # blank DistanceStamp (common) is kept as a column.
            if len(cells) > 6 and cells[-1].strip() == "":
                cells = cells[:-1]
            if len(cells) < 6:
                skipped.append(Skipped(path, line_no, "too few columns"))
                log.debug("skip %s:%d", path, line_no)
                continue
            message = ",".join(cells[2:-3]).strip()
            m = _CODE.match(message)
            msgs.append(StatusMessage(
                run=RunId.parse(cells[0]), severity=cells[1].strip(), message=message,
                module=cells[-3].strip(), time=_time(cells[-2]), time_text=cells[-2].strip(),
                distance=to_float(cells[-1]), code=int(m.group(1)) if m else None,
            ))
    return msgs, skipped
