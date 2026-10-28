"""The per-photo list: one record per photo file, for the audit CSV (Phase 4 writes it)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from qcdata.core.loader import DayTiming

COLUMNS = ("day", "run", "view", "filename", "photo_number", "pulse_number", "pulse_device_us",
           "gps_utc", "pc_time", "local_time", "time_source", "gap_from_previous_s", "flags")


@dataclass(frozen=True)
class PhotoRecord:
    day: str
    run: str
    view: str
    filename: str
    photo_number: int
    pulse_number: int | None
    pulse_device_us: int | None
    gps_utc: str
    pc_time: str
    local_time: str
    time_source: str
    gap_from_previous_s: str
    flags: str

    def as_row(self) -> list[str]:
        return [str(getattr(self, c)) if getattr(self, c) is not None else "" for c in COLUMNS]


def _iso_utc(t: float | None) -> str:
    return "" if t is None else datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + "Z"


def records(day: str, timing: DayTiming) -> list[PhotoRecord]:
    out: list[PhotoRecord] = []
    for run in sorted(timing.runs):
        for view in sorted(timing.runs[run]):
            prev = None
            for p in timing.runs[run][view].photos:
                gap = "" if (p.gps_utc is None or prev is None) else f"{p.gps_utc - prev:.3f}"
                if p.gps_utc is not None:
                    prev = p.gps_utc
                out.append(PhotoRecord(
                    day=day, run=str(run), view=view, filename=f"{p.name_mm:012d}.jpg",
                    photo_number=p.photo_number, pulse_number=p.pulse_number,
                    pulse_device_us=p.pulse_device_us, gps_utc=_iso_utc(p.gps_utc),
                    pc_time=p.pc_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] if p.pc_time else "",
                    local_time=p.local_time.isoformat(timespec="milliseconds") if p.local_time else "",
                    time_source=p.time_source, gap_from_previous_s=gap, flags=";".join(p.flags)))
    return out
