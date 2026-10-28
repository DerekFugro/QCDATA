"""Plain data objects shared by every part of the engine.

Parsers build these; checks read them. Nothing here does I/O or judges data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

# A run id ("UniqueRun"): YYYYMMDD.HHMMSS, bracketed in CSVs, bare as a folder name.
_RUN_ID_RE = re.compile(r"^\s*\[?(\d{8})\.(\d{6})\]?\s*$")


@dataclass(frozen=True, order=True)
class RunId:
    """Canonical run id, always stored bare: '20261017.153218'."""

    value: str

    @classmethod
    def parse(cls, text: str | None) -> RunId | None:
        """Accept '[20261017.153218]' or '20261017.153218'; return None otherwise."""
        if text is None:
            return None
        m = _RUN_ID_RE.match(text)
        if not m:
            return None
        hhmmss = m.group(2)
        if int(hhmmss[:2]) > 23 or int(hhmmss[2:4]) > 59 or int(hhmmss[4:]) > 59:
            return None
        return cls(f"{m.group(1)}.{hhmmss}")

    @property
    def day(self) -> str:
        """The collection day, 'YYYYMMDD'."""
        return self.value[:8]

    @property
    def seconds_of_day(self) -> int:
        h, m, s = int(self.value[9:11]), int(self.value[11:13]), int(self.value[13:15])
        return h * 3600 + m * 60 + s

    @property
    def bracketed(self) -> str:
        return f"[{self.value}]"

    def within(self, other: RunId, tolerance_s: int) -> bool:
        """Same day and at most `tolerance_s` seconds apart."""
        return self.day == other.day and abs(self.seconds_of_day - other.seconds_of_day) <= tolerance_s

    def __str__(self) -> str:
        return self.value


class Severity(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"

    @property
    def rank(self) -> int:
        return {"PASS": 0, "WARN": 1, "FAIL": 2}[self.value]


@dataclass(frozen=True)
class Skipped:
    """A line a parser could not use, and why. Never raised as an error."""

    path: Path
    line_no: int
    reason: str


# ---------------------------------------------------------------- export log
@dataclass(frozen=True)
class ExportRow:
    run: RunId
    section: str
    begin_distance_m: float | None
    end_distance_m: float | None
    begin_chainage_km: float | None
    end_chainage_km: float | None
    source: Path


@dataclass
class ExportLog:
    path: Path
    title: str
    start_date: str | None
    end_date: str | None
    rows: list[ExportRow] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)


# ---------------------------------------------------------------- daily
@dataclass(frozen=True)
class DailyRow:
    run: RunId | None          # None for a "[0]" row (a section with no run)
    raw_filename: str
    section: str
    status: str                # "C", "V", "X", or whatever the file says
    comment: str
    comment_kind: str          # "delete", "collected_short", "other", "" (none)
    initials: str
    length_km: float | None
    collected_length_km: float | None
    gps_mode: str
    lat_beg: float | None
    long_beg: float | None
    date_text: str
    line_no: int

    @property
    def is_checked(self) -> bool:
        """C (collected) and V (verification) runs are checked; X is not."""
        return self.run is not None and self.status in ("C", "V")


@dataclass
class DailyFile:
    path: Path
    day: str
    rows: list[DailyRow] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)   # acs_version, report_version, time_in_motion
    skipped: list[Skipped] = field(default_factory=list)

    @property
    def run_rows(self) -> list[DailyRow]:
        return [r for r in self.rows if r.run is not None]


# ---------------------------------------------------------------- status messages
@dataclass(frozen=True)
class StatusMessage:
    run: RunId | None
    severity: str
    message: str
    module: str
    time: datetime | None
    time_text: str
    distance: float | None
    code: int | None           # leading number of e.g. "9057 - Camera ROW ..."


# ---------------------------------------------------------------- photos
@dataclass(frozen=True)
class PhotoSequence:
    """One run's photos for one view, from file NAMES only (never opened)."""

    run: RunId
    view: str                  # "ROW" or "Rear"
    folder: Path
    names_mm: tuple[int, ...]  # sorted filename numbers (photo count x step)
    step_mm: int | None        # most common gap; None if fewer than 2 photos
    missing_mm: tuple[int, ...]  # gaps in the sequence between first and last
    other_files: tuple[str, ...]  # anything in the folder that isn't a photo

    @property
    def count(self) -> int:
        return len(self.names_mm)

    def photo_number(self, name_mm: int) -> int | None:
        if not self.step_mm:
            return 1 if self.names_mm and name_mm == self.names_mm[0] else None
        return name_mm // self.step_mm


# ---------------------------------------------------------------- lasers
@dataclass(frozen=True)
class LaserFile:
    run: RunId
    side: str                  # "L" or "R"
    path: Path
    exists: bool
    rows: int
    frame_gaps: tuple[tuple[int, int], ...]   # (frameIndex before, frameIndex after)
    missing_frames: int
    first_ptp_us: int | None   # after any PTP-lock rows at the start
    last_ptp_us: int | None
    lock_rows_skipped: int
    skipped_lines: int

    @property
    def state(self) -> str:
        if not self.exists:
            return "missing"
        return "empty" if self.rows == 0 else "present"


# ---------------------------------------------------------------- SBG
@dataclass
class SbgRun:
    """One DataLogger folder: pulses and the device-time -> UTC table."""

    folder_run: RunId          # from the folder name (may be 1 s off the run)
    folder: Path
    pulses_us: list[int]       # eventOutA, unwrapped device microseconds
    pulses_b_us: list[int] | None
    responses_us: list[int] | None   # eventInA
    utc_table: list[tuple[int, float]]  # (unwrapped device us, UTC epoch s)
    rollovers: int             # counter rollovers seen in eventOutA
    skipped_lines: int


# ---------------------------------------------------------------- logs
@dataclass(frozen=True)
class CameraEvent:
    kind: str                  # "start_in", "start_out", "stop_in"
    pc_time: datetime          # PC display time, naive
    source: Path


@dataclass(frozen=True)
class FrameLine:
    pc_time: datetime          # PC display time, naive
    frame_id: int
    run: RunId
    view: str
    name_mm: int
    mil_err: int
    event_timestamp: float | None
    source: Path


@dataclass(frozen=True)
class OffsetSample:
    """One SBG.log CallbackUtc line."""

    pc_time: datetime          # PC display time of the line, naive
    hw_unix: float             # GPS-derived UTC, seconds
    pc_unix: float
    delta_s: float             # PC minus HW (positive = PC ahead)

    @property
    def display_minus_utc_s(self) -> float:
        """What to add to a true UTC epoch to get the PC's displayed time (as epoch)."""
        from calendar import timegm

        return timegm(self.pc_time.timetuple()) + self.pc_time.microsecond / 1e6 - self.hw_unix


# ---------------------------------------------------------------- QC_Video / settings
@dataclass(frozen=True)
class QcVideoRow:
    run: RunId
    error: str
    view: str
    first_file: str
    last_file: str
    begin_km: float | None
    end_km: float | None
    image_count: int | None
    note: str
    source: Path


@dataclass(frozen=True)
class SettingsInfo:
    path: Path
    acs_version: str | None
    van_name: str | None
    parsed: bool
    error: str | None
