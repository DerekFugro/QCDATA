"""ARAN01_Export_<stamp>_log.csv - the run list of one export.

Format: a title line, 'Start Date: ...', 'End Date: ...', a blank line, then a
'UniqueRun,SectionName,BeginDistanceStamp,EndDistanceStamp,BeginChainage,EndChainage'
header (sometimes with a trailing comma) and one row per section.

Only files with that header are run lists. ExportLogs\\*_export_log.csv files are
export *process* logs and are not parsed here.
"""

from __future__ import annotations

import csv
from pathlib import Path

from qcdata.core.model import ExportLog, ExportRow, RunId, Skipped
from qcdata.core.parsers._util import log, strip_trailing_empty, to_float


def parse_run_list(path: Path) -> ExportLog:
    path = Path(path)
    result = ExportLog(path=path, title="", start_date=None, end_date=None)
    in_rows = False
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        for line_no, cells in enumerate(csv.reader(fh), start=1):
            cells = strip_trailing_empty(cells)
            if not cells:
                continue
            first = cells[0].strip()
            if not in_rows:
                low = first.lower()
                if low.startswith("start date:"):
                    result.start_date = first.split(":", 1)[1].strip()
                elif low.startswith("end date:"):
                    result.end_date = first.split(":", 1)[1].strip()
                elif low == "uniquerun":
                    in_rows = True
                elif not result.title:
                    result.title = first
                continue
            run = RunId.parse(first)
            if run is None or len(cells) < 2:
                result.skipped.append(Skipped(path, line_no, f"not a run row: {first[:40]!r}"))
                log.debug("skip %s:%d", path, line_no)
                continue
            get = lambda i: cells[i] if i < len(cells) else None  # noqa: E731
            result.rows.append(ExportRow(
                run=run, section=cells[1].strip(),
                begin_distance_m=to_float(get(2)), end_distance_m=to_float(get(3)),
                begin_chainage_km=to_float(get(4)), end_chainage_km=to_float(get(5)),
                source=path,
            ))
    if not in_rows:
        result.skipped.append(Skipped(path, 0, "no UniqueRun header - not a run list"))
    return result


def collect_runs(logs: list[ExportLog]) -> dict[str, dict[RunId, list[ExportRow]]]:
    """All export rows by day (from the run id) and run, with duplicates removed.

    The same export is often copied to more than one place, and a day can be
    exported more than once; both are handled here.
    """
    by_day: dict[str, dict[RunId, list[ExportRow]]] = {}
    seen: set[tuple] = set()
    for el in logs:
        for row in el.rows:
            key = (row.run, row.section, row.begin_distance_m, row.end_distance_m)
            if key in seen:
                continue
            seen.add(key)
            by_day.setdefault(row.run.day, {}).setdefault(row.run, []).append(row)
    return by_day
