"""Shared pulse arithmetic for C8, C10, C15 and C16."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from qcdata.config.schema import Config
from qcdata.core.loader import DayData, RunData
from qcdata.core.model import LaserFile, PhotoSequence
from qcdata.core.parsers.sbg import UtcConverter
from qcdata.core.photo_times import PcClock, naive_epoch


def pulse_utcs(rd: RunData) -> list[float]:
    """UTC of each photo-producing pulse, in order."""
    if not (rd.sbg and rd.pulse_plan and rd.sbg.utc_table):
        return []
    conv = UtcConverter(rd.sbg.utc_table)
    out = [conv.to_utc(p) for p in rd.pulse_plan.photo_pulses_us]
    return [u for u in out if u is not None]


def pc_to_utc(clock: PcClock, pc: datetime | None) -> float | None:
    """A PC display time -> true UTC, using the day's PC clock."""
    if pc is None or not clock:
        return None
    guess = naive_epoch(pc) - clock.samples[0][1]
    off = clock.display_minus_utc(guess)
    return None if off is None else naive_epoch(pc) - off


@dataclass(frozen=True)
class PhotoPulseResult:
    photos: int
    expected: int            # photo-producing pulses + 1
    raw_pulses: int
    no_photo_pulses: int
    pulses_before_camera_start: int | None   # None = camera log not available
    pulses_after_camera_stop: int | None

    @property
    def diff(self) -> int:
        return self.photos - self.expected

    @property
    def short(self) -> int:
        return max(0, -self.diff)


def photo_vs_pulses(rd: RunData, seq: PhotoSequence, day: DayData) -> PhotoPulseResult | None:
    if not (rd.sbg and rd.pulse_plan):
        return None
    utcs = pulse_utcs(rd)
    start = pc_to_utc(day.clock, rd.camera_start_out)
    stop = pc_to_utc(day.clock, rd.camera_stop_in)
    before = sum(1 for u in utcs if u < start) if start is not None and utcs else None
    after = sum(1 for u in utcs if u > stop) if stop is not None and utcs else None
    return PhotoPulseResult(seq.count, len(rd.pulse_plan.photo_pulses_us) + 1,
                            rd.pulse_plan.raw_count, len(rd.pulse_plan.no_photo_pulses), before, after)


@dataclass(frozen=True)
class LaserPulseResult:
    pulses_before_first_row: int
    pulses_after_last_row: int


def laser_vs_pulses(rd: RunData, lf: LaserFile, cfg: Config) -> LaserPulseResult | None:
    utcs = pulse_utcs(rd)
    if not utcs or lf.first_ptp_us is None or lf.last_ptp_us is None:
        return None
    first = lf.first_ptp_us / 1e6 - cfg.tai_minus_utc_s
    last = lf.last_ptp_us / 1e6 - cfg.tai_minus_utc_s
    return LaserPulseResult(sum(1 for u in utcs if u < first), sum(1 for u in utcs if u > last))
