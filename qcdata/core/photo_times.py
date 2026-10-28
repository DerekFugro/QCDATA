"""When each photo was taken - rebuilt from its camera pulse.

File dates can't be used (copies reset them) and photos carry no time. So:
  1. photo 1 is a start-up frame with no pulse; photo k (k >= 2) <-> pulse k-1,
     after dropping pulses that came < min_pulse_gap_s after the previous one
     (those get no photo);
  2. pulse device time -> GPS UTC via the DataLogger's utcTime table;
  3. UTC -> the PC's displayed time (what the van would have stamped on the
     file) using the day's offset from SBG.log CallbackUtc lines, or, if SBG.log
     is missing, the camera log's FrameID lines;
  4. UTC -> true local time with zoneinfo.
Every camera-log FrameID line (every 100th photo) is used as a self-check.
"""

from __future__ import annotations

import bisect
import calendar
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from qcdata.core.model import FrameLine, OffsetSample, PhotoSequence, RunId, SbgRun
from qcdata.core.parsers.sbg import UtcConverter

_EPOCH = datetime(1970, 1, 1)


def naive_epoch(dt: datetime) -> float:
    """A naive datetime read as if it were UTC, as epoch seconds."""
    return calendar.timegm(dt.timetuple()) + dt.microsecond / 1e6


def from_naive_epoch(seconds: float) -> datetime:
    return _EPOCH + timedelta(seconds=seconds)


@dataclass(frozen=True)
class PulsePlan:
    """A run's pulses split into those that produced a photo and those that didn't."""

    photo_pulses_us: tuple[int, ...]     # in order; photo k <-> photo_pulses_us[k-2]
    no_photo_pulses: tuple[int, ...]     # indices (in the raw list) of dropped pulses
    raw_count: int


def plan_pulses(pulses_us: list[int], min_gap_s: float) -> PulsePlan:
    kept: list[int] = []
    dropped: list[int] = []
    min_gap_us = min_gap_s * 1e6
    for i, p in enumerate(pulses_us):
        if kept and p - kept[-1] < min_gap_us:
            dropped.append(i)
            continue
        kept.append(p)
    return PulsePlan(tuple(kept), tuple(dropped), len(pulses_us))


class PcClock:
    """UTC -> PC displayed time. Source: 'sbg_log', 'frame_lines', or None."""

    def __init__(self, samples: list[tuple[float, float]], source: str | None):
        self.samples = sorted(samples)            # (utc, display_minus_utc)
        self.source = source
        self._utc = [s[0] for s in self.samples]

    @classmethod
    def from_sbg_log(cls, offsets: list[OffsetSample]) -> PcClock:
        return cls([(o.hw_unix, o.display_minus_utc_s) for o in offsets], "sbg_log" if offsets else None)

    def __bool__(self) -> bool:
        return bool(self.samples)

    def display_minus_utc(self, utc: float) -> float | None:
        if not self.samples:
            return None
        j = bisect.bisect_left(self._utc, utc)
        cands = [self.samples[k] for k in (j - 1, j) if 0 <= k < len(self.samples)]
        return min(cands, key=lambda s: abs(s[0] - utc))[1]

    def pc_time(self, utc: float) -> datetime | None:
        off = self.display_minus_utc(utc)
        return None if off is None else from_naive_epoch(utc + off)


@dataclass(frozen=True)
class PhotoTime:
    run: RunId
    view: str
    name_mm: int
    photo_number: int
    pulse_number: int | None          # 1-based among photo-producing pulses
    pulse_device_us: int | None
    gps_utc: float | None
    pc_time: datetime | None
    local_time: datetime | None
    time_source: str                  # pulse | startup_frame | unverified | none
    flags: tuple[str, ...]


def photo_number(seq: PhotoSequence, name_mm: int, fallback_step: int) -> int:
    step = seq.step_mm or fallback_step
    return max(1, name_mm // step)


def time_photos(seq: PhotoSequence, sbg: SbgRun | None, plan: PulsePlan | None, clock: PcClock,
                tz: ZoneInfo, fallback_step: int, startup_pc_time: datetime | None,
                verified: bool, stop_s: float) -> list[PhotoTime]:
    conv = UtcConverter(sbg.utc_table) if sbg else None
    dropped_after: set[int] = set()
    if plan and sbg and plan.no_photo_pulses:
        # photo pulse index just after each dropped pulse
        kept = list(plan.photo_pulses_us)
        for raw_i in plan.no_photo_pulses:
            p = sbg.pulses_us[raw_i]
            dropped_after.add(bisect.bisect_right(kept, p))
    out: list[PhotoTime] = []
    prev_utc: float | None = None
    for name in seq.names_mm:
        k = photo_number(seq, name, fallback_step)
        flags: list[str] = []
        if k == 1:
            flags.append("startup_frame")
            out.append(PhotoTime(seq.run, seq.view, name, k, None, None, None, startup_pc_time,
                                 None, "startup_frame", tuple(flags)))
            continue
        idx = k - 2
        if not plan or not conv or idx >= len(plan.photo_pulses_us):
            out.append(PhotoTime(seq.run, seq.view, name, k, None, None, None, None, None,
                                 "none", ("no_pulse",)))
            continue
        dev = plan.photo_pulses_us[idx]
        utc = conv.to_utc(dev)
        if idx in dropped_after:
            flags.append("after_no_photo_pulse")
        if prev_utc is not None and utc is not None and utc - prev_utc >= stop_s:
            flags.append("after_stop")
        prev_utc = utc if utc is not None else prev_utc
        local = datetime.fromtimestamp(utc, timezone.utc).astimezone(tz) if utc is not None else None
        out.append(PhotoTime(seq.run, seq.view, name, k, idx + 1, dev, utc,
                             clock.pc_time(utc) if utc is not None else None, local,
                             "pulse" if verified else "unverified", tuple(flags)))
    return out


def frame_line_residuals(frames: list[FrameLine], seq: PhotoSequence, sbg: SbgRun,
                         plan: PulsePlan, clock: PcClock, fallback_step: int) -> list[float]:
    """For each FrameID line of this run/view: logged PC time minus computed PC time."""
    conv = UtcConverter(sbg.utc_table)
    out = []
    for fl in frames:
        if fl.run != seq.run or fl.view.lower() != seq.view.lower():
            continue
        k = fl.name_mm // (seq.step_mm or fallback_step)
        if k < 2 or k - 2 >= len(plan.photo_pulses_us):
            continue
        utc = conv.to_utc(plan.photo_pulses_us[k - 2])
        off = clock.display_minus_utc(utc) if utc is not None else None
        if utc is None or off is None:
            continue
        out.append(naive_epoch(fl.pc_time) - (utc + off))
    return out


def offset_from_frame_lines(pairs: list[tuple[float, datetime]]) -> PcClock:
    """Fallback clock from (pulse UTC, logged PC time) pairs: the median offset."""
    if not pairs:
        return PcClock([], None)
    offs = [naive_epoch(pc) - utc for utc, pc in pairs]
    med = statistics.median(offs)
    return PcClock([(utc, med) for utc, _ in pairs], "frame_lines")
