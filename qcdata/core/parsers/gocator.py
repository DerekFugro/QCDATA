"""Laser files - GoCatorData/<run>/<run with T>L.csv and ...R.csv.

Rows are very wide (tens of kB); only the first four columns are read:
frameIndex, timestamp (sensor clock), ptpTimestamp (TAI, microseconds), encoder.
Missing, empty, and present are told apart; frameIndex gaps are counted.
"""

from __future__ import annotations

import os
from pathlib import Path

from qcdata.core.model import LaserFile, RunId

# PTP can jump while it locks at the start of a file. On 2026-10-17 it never did,
# and every large gap was a real stop, so only a backwards step or a step longer
# than this, within the first rows, counts as a lock jump.
LOCK_WINDOW_ROWS = 20
LOCK_JUMP_US = 3600 * 1_000_000


def laser_path(run_dir: Path, run: RunId, side: str) -> Path:
    want = f"{run.value.replace('.', 'T')}{side}.csv"
    exact = run_dir / want
    if exact.exists():
        return exact
    try:
        with os.scandir(run_dir) as it:
            for e in it:
                if e.is_file() and e.name.lower() == want.lower():
                    return Path(e.path)
    except OSError:
        pass
    return exact


def parse_laser(run: RunId, side: str, path: Path) -> LaserFile:
    path = Path(path)
    if not path.exists():
        return LaserFile(run, side, path, False, 0, (), 0, None, None, 0, 0)
    rows = 0
    skipped = 0
    gaps: list[tuple[int, int]] = []
    missing = 0
    prev_frame: int | None = None
    early_ptp: list[int] = []
    last_ptp: int | None = None
    with open(path, "rb") as fh:
        fh.readline()  # header
        for line in fh:
            cells = line.split(b",", 4)
            if len(cells) < 4:
                skipped += 1
                continue
            try:
                frame = int(cells[0])
                ptp = int(cells[2])
            except ValueError:
                skipped += 1
                continue
            rows += 1
            if prev_frame is not None and frame != prev_frame + 1:
                gaps.append((prev_frame, frame))
                if frame > prev_frame:
                    missing += frame - prev_frame - 1
            prev_frame = frame
            if len(early_ptp) <= LOCK_WINDOW_ROWS:
                early_ptp.append(ptp)
            last_ptp = ptp
    lock = 0
    for i in range(1, len(early_ptp)):
        step = early_ptp[i] - early_ptp[i - 1]
        if step < 0 or step > LOCK_JUMP_US:
            lock = i
    first_ptp = early_ptp[lock] if early_ptp else None
    return LaserFile(run, side, path, True, rows, tuple(gaps), missing, first_ptp,
                     last_ptp, lock, skipped)
