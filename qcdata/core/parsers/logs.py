"""ACS logs: the camera log (<PC>-VideoLogCXP.log) and the SBG log
(<PC>-Server-SBG.log). Streamed line by line; filtered by DATE.

Camera log lines used:
  2026-10-17 14:19:47,688 0x00001aac root - VC2_StartAcquisition in
  ... root - ProcessingFunction, FrameID: 100, EventTimeStamp: 6549.1694, MilErr: 0,
      File: \\\\ARAN01-SERVER\\Removable1\\Images\\20261017.151845\\Rear\\000000075000.jpg
SBG log lines used:
  INFO 2026-10-17 11:57:30.555 [22] - CallbackUtc, TS HWUnix: 1792252599 (s),
      TS PCUnix: 1792256250.555, Delta TSUnix PC vs HW: 3651.555 (PC ahead), ...
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path, PureWindowsPath

from qcdata.core.discovery import LogFile
from qcdata.core.model import CameraEvent, FrameLine, OffsetSample, RunId

_CAM_LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d{3}) .*? - (.*)$")
_FRAME = re.compile(
    r"ProcessingFunction, FrameID: (\d+), EventTimeStamp: ([-\d.]+), MilErr: (-?\d+), File: (.+?)\s*$")
_EVENTS = {"VC2_StartAcquisition in": "start_in", "VC2_StartAcquisition out": "start_out",
           "VC2_StopAcquisition in": "stop_in"}
_SBG = re.compile(
    r"^\S+\s+(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s.*?CallbackUtc, TS HWUnix: ([\d.]+) \(s\), "
    r"TS PCUnix: ([\d.]+), Delta TSUnix PC vs HW: (-?[\d.]+)")
SBG_SAMPLE_EVERY_S = 30


def _days_match(stamp: str, days: set[str] | None) -> bool:
    return days is None or stamp[:10].replace("-", "") in days


def parse_camera_logs(files: list[LogFile], days: set[str] | None = None
                      ) -> tuple[list[CameraEvent], list[FrameLine]]:
    events: list[CameraEvent] = []
    frames: list[FrameLine] = []
    for lf in files:
        if lf.kind.lower() != "videologcxp":
            continue
        with open(lf.path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "Acquisition" not in line and "FrameID" not in line:
                    continue
                m = _CAM_LINE.match(line)
                if not m or not _days_match(m.group(1), days):
                    continue
                when = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(
                    microsecond=int(m.group(2)) * 1000)
                body = m.group(3).strip()
                if body in _EVENTS:
                    events.append(CameraEvent(_EVENTS[body], when, lf.path))
                    continue
                f = _FRAME.search(body)
                if not f:
                    continue
                p = PureWindowsPath(f.group(4))
                run = RunId.parse(p.parent.parent.name)
                stem = p.stem
                if run is None or not stem.isdigit():
                    continue
                try:
                    ets = float(f.group(2))
                except ValueError:
                    ets = None
                frames.append(FrameLine(when, int(f.group(1)), run, p.parent.name, int(stem),
                                        int(f.group(3)), ets, lf.path))
    # The same lines can appear in more than one copy; keep each once, in time order.
    uniq_events: dict[tuple, CameraEvent] = {}
    for ev in events:
        uniq_events.setdefault((ev.pc_time, ev.kind), ev)
    events = sorted(uniq_events.values(), key=lambda e: (e.pc_time, e.kind))
    uniq: dict[tuple, FrameLine] = {}
    for fl in frames:
        uniq.setdefault((fl.pc_time, fl.run, fl.view, fl.frame_id), fl)
    return events, sorted(uniq.values(), key=lambda f: (f.pc_time, f.view))


def parse_sbg_offsets(files: list[LogFile], days: set[str] | None = None) -> list[OffsetSample]:
    """CallbackUtc samples, one kept per SBG_SAMPLE_EVERY_S seconds per file."""
    out: list[OffsetSample] = []
    for lf in files:
        if lf.kind.lower() != "sbg":
            continue
        last_kept: datetime | None = None
        with open(lf.path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "CallbackUtc" not in line:
                    continue
                m = _SBG.match(line)
                if not m or not _days_match(m.group(1), days):
                    continue
                when = datetime.strptime(m.group(1)[:26], "%Y-%m-%d %H:%M:%S.%f")
                if last_kept is not None and 0 <= (when - last_kept).total_seconds() < SBG_SAMPLE_EVERY_S:
                    continue
                last_kept = when
                hw, pc = float(m.group(2)), float(m.group(3))
                out.append(OffsetSample(when, hw, pc, pc - hw))
    uniq = {(s.pc_time, s.hw_unix): s for s in out}
    return sorted(uniq.values(), key=lambda s: s.pc_time)
