"""Write the report files. Every file goes through WriteGuard.create_new, so
QCDATA only ever ADDS files - never overwrites, never touches anything else."""

from __future__ import annotations

import csv
import io
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from qcdata.core import inventory
from qcdata.core.engine import CheckRun
from qcdata.core.paths import WriteGuard
from qcdata.core.report.render import render_html

CSV_HEADER_NOTE = (
    "# QCDATA per-photo list. One row per photo file. No time here comes from a file date "
    "(the files were copied, so their dates are the copy time).",
    "# gps_utc: the GPS time of the camera trigger pulse (SBG eventOutA), accurate to about 1 ms.",
    "# pc_time: that moment on the van PC's clock - the closest thing to the photo's original "
    "creation time. Accurate to about 0.1 s (PC clock offset taken from SBG.log, or from the camera log's FrameID lines).",
    "# local_time: gps_utc in the local time zone. time_source: pulse, startup_frame, unverified, or none.",
    "# Photo 1 of each run is a start-up frame taken before the first pulse; it has no pulse time.",
)


@dataclass
class Written:
    html: Path | None = None
    json: Path | None = None
    csv: Path | None = None


def folder_label(target: Path) -> str:
    """The <name> in the file names: the folder name, or for a drive root its
    volume label (else the drive letter)."""
    p = Path(target)
    if p.name:
        return _safe(p.name)
    label = _volume_label(p) if sys.platform == "win32" else ""
    return _safe(label or p.drive.rstrip(":\\/") or "drive")


def _volume_label(root: Path) -> str:
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(261)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(str(root), buf, 261, None, None, None, None, 0)
        return buf.value if ok else ""
    except Exception:  # noqa: BLE001 - a label is a nicety
        return ""


def _safe(name: str) -> str:
    keep = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name).strip("._")
    return keep[:60] or "folder"


def json_bytes(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n").encode("utf-8")


def csv_bytes(result: CheckRun) -> bytes:
    buf = io.StringIO(newline="")
    for line in CSV_HEADER_NOTE:
        buf.write(line + "\r\n")
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(inventory.COLUMNS)
    for day in sorted(result.days):
        for rec in inventory.records(day, result.days[day].timing):
            w.writerow(rec.as_row())
    # utf-8-sig so Excel opens it with the right encoding.
    return buf.getvalue().encode("utf-8-sig")


def write_reports(result: CheckRun, data: dict[str, Any], guard: WriteGuard,
                  when: datetime, *, with_csv: bool = True) -> Written:
    stamp = f"{when:%Y%m%d-%H%M%S}"
    name = folder_label(result.target)
    out = Written()
    csv_name = f"images_{name}_{stamp}.csv"
    if with_csv:
        out.csv = guard.create_new(csv_name, csv_bytes(result))
        csv_name = out.csv.name
    out.json = guard.create_new(f"findings_{name}_{stamp}.json", json_bytes(data))
    html = render_html(data, csv_name if with_csv else None, out.json.name)
    out.html = guard.create_new(f"QCDATA_Report_{name}_{stamp}.html", html.encode("utf-8"))
    return out
