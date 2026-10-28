"""SBG DataLogger files - SBGData/<yymmdd>/<run> DataLogger/.

eventOutA.txt (camera pulses), eventOutB.txt / eventInA.txt (cross-check only),
utcTime.txt (device time -> GPS UTC, 1 Hz). Only these are read.

Two traps, both hit during spec research:
- Timestamps are right-aligned: fewer digits means leading spaces. Rows are
  parsed with split(); any row whose first token is an integer is a data row.
- The device timestamp is a 32-bit microsecond counter that rolls over every
  4 294.967 296 s (~71.6 min). Every series is unwrapped, then aligned to the
  utcTime table so pulses and UTC sit on the same continuous clock.
"""

from __future__ import annotations

import bisect
import calendar
from pathlib import Path

from qcdata.core.model import RunId, SbgRun

WRAP = 2**32


def unwrap(values: list[int]) -> tuple[list[int], int]:
    """Undo 32-bit rollovers in a time-ordered series. Returns (values, rollovers)."""
    out: list[int] = []
    add = 0
    rollovers = 0
    prev = None
    for v in values:
        if prev is not None and v < prev - WRAP // 2:
            add += WRAP
            rollovers += 1
        prev = v
        out.append(v + add)
    return out, rollovers


def _rows(path: Path) -> tuple[list[list[str]], int]:
    rows: list[list[str]] = []
    skipped = 0
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            t = line.split()
            if not t:
                continue
            if t[0].isdigit():
                rows.append(t)
            elif not t[0].startswith(("timestamp", "(")):
                skipped += 1
    return rows, skipped


def parse_event_file(path: Path) -> tuple[list[int], int, int]:
    """(unwrapped device microseconds, rollovers, skipped lines)."""
    rows, skipped = _rows(path)
    values, rollovers = unwrap([int(r[0]) for r in rows])
    return values, rollovers, skipped


def parse_utc_file(path: Path) -> tuple[list[tuple[int, float]], int]:
    """[(unwrapped device us, UTC epoch seconds)], skipped. Rows without a valid
    date (year before 2000) are left out."""
    rows, skipped = _rows(path)
    raw: list[tuple[int, float]] = []
    for r in rows:
        try:
            y, mo, d, h, mi, s = (int(x) for x in r[3:9])
            ns = int(r[9])
        except (IndexError, ValueError):
            skipped += 1
            continue
        if y < 2000:
            skipped += 1
            continue
        raw.append((int(r[0]), calendar.timegm((y, mo, d, h, mi, s)) + ns / 1e9))
    dev, _ = unwrap([x[0] for x in raw])
    return [(dv, u) for dv, (_, u) in zip(dev, raw)], skipped


def align(series: list[int], table: list[tuple[int, float]]) -> list[int]:
    """Shift a separately-unwrapped series by whole rollovers so it lands on the
    utcTime table's clock."""
    if not series or not table:
        return series
    lo, hi = table[0][0], table[-1][0]
    best_k, best_d = 0, None
    for k in range(-3, 4):
        v = series[0] + k * WRAP
        d = 0 if lo <= v <= hi else min(abs(v - lo), abs(v - hi))
        if best_d is None or d < best_d:
            best_k, best_d = k, d
    return [v + best_k * WRAP for v in series]


class UtcConverter:
    """Device microseconds -> UTC epoch seconds, by linear interpolation between
    the 1 Hz utcTime rows (extrapolating from the end pairs if outside)."""

    def __init__(self, table: list[tuple[int, float]]):
        self.table = table
        self._dev = [t[0] for t in table]

    def __bool__(self) -> bool:
        return len(self.table) >= 2

    def to_utc(self, dev_us: int) -> float | None:
        if len(self.table) < 2:
            return None
        j = bisect.bisect_left(self._dev, dev_us)
        j = max(1, min(len(self.table) - 1, j))
        (a, ta), (b, tb) = self.table[j - 1], self.table[j]
        return ta + (dev_us - a) * (tb - ta) / (b - a) if b != a else ta


def load_sbg_run(folder_run: RunId, folder: Path) -> SbgRun:
    folder = Path(folder)
    utc_path = folder / "utcTime.txt"
    table, skipped = parse_utc_file(utc_path) if utc_path.exists() else ([], 0)
    pulses: list[int] = []
    rollovers = 0
    a_path = folder / "eventOutA.txt"
    if a_path.exists():
        pulses, rollovers, s = parse_event_file(a_path)
        skipped += s
        pulses = align(pulses, table)
    extra: dict[str, list[int] | None] = {}
    for name in ("eventOutB.txt", "eventInA.txt"):
        p = folder / name
        if p.exists():
            vals, _, s = parse_event_file(p)
            skipped += s
            extra[name] = align(vals, table)
        else:
            extra[name] = None
    return SbgRun(folder_run=folder_run, folder=folder, pulses_us=pulses,
                  pulses_b_us=extra["eventOutB.txt"], responses_us=extra["eventInA.txt"],
                  utc_table=table, rollovers=rollovers, skipped_lines=skipped)
