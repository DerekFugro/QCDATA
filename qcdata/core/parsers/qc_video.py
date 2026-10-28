"""QC_Video.csv - the collection software's tail check, read so QCDATA can verify it.

Header: Session Name,Error,View,First File,Last File,Begin Chainage,End Chainage,Image Count
(sometimes with a trailing comma). 'First File' is the last photo that exists;
'Last File' is the run's end distance written as a fake filename; chainages are
kilometres. An optional 9th column holds a hand-written note. QCDATA never writes
this file.
"""

from __future__ import annotations

import csv
from pathlib import Path

from qcdata.core.model import QcVideoRow, RunId, Skipped
from qcdata.core.parsers._util import strip_trailing_empty, to_float, to_int


def parse_qc_video(path: Path) -> tuple[list[QcVideoRow], list[Skipped]]:
    path = Path(path)
    rows: list[QcVideoRow] = []
    skipped: list[Skipped] = []
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        for line_no, cells in enumerate(csv.reader(fh), start=1):
            if line_no == 1:
                continue
            cells = strip_trailing_empty(cells)
            if not cells:
                continue
            run = RunId.parse(cells[0])
            if run is None or len(cells) < 8:
                skipped.append(Skipped(path, line_no, "not a QC_Video row"))
                continue
            rows.append(QcVideoRow(
                run=run, error=cells[1].strip(), view=cells[2].strip(),
                first_file=cells[3].strip(), last_file=cells[4].strip(),
                begin_km=to_float(cells[5]), end_km=to_float(cells[6]),
                image_count=to_int(cells[7]), note=",".join(cells[8:]).strip(), source=path,
            ))
    return rows, skipped
