"""Assemble everything known about the chosen days into plain objects.

Reads only; judges nothing. The checks (Phase 3) work from DayData.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from qcdata.config.schema import Config
from qcdata.core.discovery import DayFolder, Manifest, match_datalogger
from qcdata.core.model import (CameraEvent, DailyFile, DailyRow, ExportRow, FrameLine, LaserFile,
                               OffsetSample, PhotoSequence, QcVideoRow, RunId, SbgRun,
                               SettingsInfo, Skipped, StatusMessage)
from qcdata.core.parsers.daily import parse_daily
from qcdata.core.parsers.export_log import collect_runs, parse_run_list
from qcdata.core.parsers.gocator import laser_path, parse_laser
from qcdata.core.parsers.images import VIEWS, find_view_dir, scan_view
from qcdata.core.parsers.logs import parse_camera_logs, parse_sbg_offsets
from qcdata.core.parsers.qc_video import parse_qc_video
from qcdata.core.parsers.sbg import UtcConverter, load_sbg_run
from qcdata.core.parsers.settings import parse_settings
from qcdata.core.parsers.status import parse_status_messages
from qcdata.core.photo_times import (PcClock, PhotoTime, PulsePlan, frame_line_residuals,
                                     offset_from_frame_lines, plan_pulses, time_photos)


def run_start_pc(run: RunId) -> datetime:
    """The run id is the PC's displayed time when the run started."""
    return datetime.strptime(run.value, "%Y%m%d.%H%M%S")


@dataclass
class RunData:
    run: RunId
    daily: DailyRow | None = None
    export_rows: list[ExportRow] = field(default_factory=list)
    in_status_messages: bool = False
    photos: dict[str, PhotoSequence | None] = field(default_factory=dict)  # view -> seq (None = no folder)
    has_image_dir: bool = False
    lasers: dict[str, LaserFile] = field(default_factory=dict)            # side -> file
    has_gocator_dir: bool = False
    sbg: SbgRun | None = None
    pulse_plan: PulsePlan | None = None
    camera_start_in: datetime | None = None
    camera_start_out: datetime | None = None
    camera_stop_in: datetime | None = None
    frame_lines: list[FrameLine] = field(default_factory=list)


@dataclass
class DayData:
    day: str
    folder: DayFolder | None
    daily: DailyFile | None
    export_found: bool
    status: list[StatusMessage]
    qc_video: list[QcVideoRow] | None
    settings: SettingsInfo | None
    runs: dict[RunId, RunData]
    camera_events: list[CameraEvent]
    offsets: list[OffsetSample]
    clock: PcClock
    sbg_day_dir_present: bool
    unmatched_dataloggers: list[RunId]
    qinertia_projects: list[RunId]
    skipped: list[Skipped] = field(default_factory=list)


def _attach_camera(rd: RunData, events: list[CameraEvent], next_start: datetime | None) -> None:
    start = run_start_pc(rd.run)
    lo, hi = start - timedelta(seconds=10), start + timedelta(seconds=120)
    s_in = next((e for e in events if e.kind == "start_in" and lo <= e.pc_time <= hi), None)
    if not s_in:
        return
    rd.camera_start_in = s_in.pc_time
    rd.camera_start_out = next((e.pc_time for e in events if e.kind == "start_out"
                                and e.pc_time >= s_in.pc_time), None)
    limit = next_start or (s_in.pc_time + timedelta(hours=6))
    rd.camera_stop_in = next((e.pc_time for e in events if e.kind == "stop_in"
                              and s_in.pc_time < e.pc_time < limit), None)


def load_days(manifest: Manifest, days: list[str], cfg: Config, *, read_lasers: bool = True
              ) -> dict[str, DayData]:
    days = [d for d in days if d in manifest.days or True]
    day_set = set(days)
    export_logs = [parse_run_list(p) for p in manifest.run_lists]
    exports = collect_runs(export_logs)
    events, frames = parse_camera_logs(manifest.acs_logs, day_set)
    offsets = parse_sbg_offsets(manifest.acs_logs, day_set)
    sbg_dirs = set(manifest.sbg_day_dirs())
    out: dict[str, DayData] = {}

    for day in days:
        folder = manifest.days.get(day)
        daily = parse_daily(folder.daily, day) if folder and folder.daily else None
        status, skipped = (parse_status_messages(folder.status_messages)
                           if folder and folder.status_messages else ([], []))
        qcv = parse_qc_video(folder.qc_video)[0] if folder and folder.qc_video else None
        settings = parse_settings(folder.settings) if folder and folder.settings else None
        day_exports = exports.get(day, {})

        run_ids: set[RunId] = set(day_exports)
        if daily:
            run_ids |= {r.run for r in daily.run_rows}
        run_ids |= {m.run for m in status if m.run and m.run.day == day}
        run_ids |= {r for r in manifest.image_runs if r.day == day}
        run_ids |= {r for r in manifest.gocator_runs if r.day == day}

        day_events = [e for e in events if e.pc_time.strftime("%Y%m%d") == day]
        starts = sorted(run_start_pc(r) for r in run_ids)
        runs: dict[RunId, RunData] = {}
        used_loggers: set[RunId] = set()
        for run in sorted(run_ids):
            rd = RunData(run=run)
            if daily:
                rd.daily = next((r for r in daily.run_rows if r.run == run), None)
            rd.export_rows = day_exports.get(run, [])
            rd.in_status_messages = any(m.run == run for m in status)
            img_dir = manifest.image_runs.get(run)
            rd.has_image_dir = img_dir is not None
            for view in VIEWS:
                vd = find_view_dir(img_dir, view) if img_dir else None
                rd.photos[view] = scan_view(run, view, vd) if vd else None
            goc_dir = manifest.gocator_runs.get(run)
            rd.has_gocator_dir = goc_dir is not None
            if goc_dir and read_lasers:
                for side in ("L", "R"):
                    rd.lasers[side] = parse_laser(run, side, laser_path(goc_dir, run, side))
            dl = match_datalogger(run, manifest.dataloggers, cfg.sbg_match_tolerance_s)
            if dl:
                used_loggers.add(dl)
                rd.sbg = load_sbg_run(dl, manifest.dataloggers[dl])
                rd.pulse_plan = plan_pulses(rd.sbg.pulses_us, cfg.thresholds.min_pulse_gap_s)
            nxt = next((s for s in starts if s > run_start_pc(run)), None)
            _attach_camera(rd, day_events, nxt)
            rd.frame_lines = [f for f in frames if f.run == run]
            runs[run] = rd

        clock = PcClock.from_sbg_log([o for o in offsets if o.pc_time.strftime("%Y%m%d") == day])
        if not clock:
            pairs = []
            for rd in runs.values():
                if not (rd.sbg and rd.pulse_plan and rd.sbg.utc_table):
                    continue
                conv = UtcConverter(rd.sbg.utc_table)
                for fl in rd.frame_lines:
                    seq = rd.photos.get(fl.view)
                    step = (seq.step_mm if seq else None) or cfg.expected_step_mm
                    k = fl.name_mm // step
                    if 2 <= k and k - 2 < len(rd.pulse_plan.photo_pulses_us):
                        utc = conv.to_utc(rd.pulse_plan.photo_pulses_us[k - 2])
                        if utc is not None:
                            pairs.append((utc, fl.pc_time))
            clock = offset_from_frame_lines(pairs)

        out[day] = DayData(
            day=day, folder=folder, daily=daily, export_found=bool(day_exports), status=status,
            qc_video=qcv, settings=settings, runs=runs, camera_events=day_events,
            offsets=[o for o in offsets if o.pc_time.strftime("%Y%m%d") == day], clock=clock,
            sbg_day_dir_present=day[2:] in sbg_dirs,
            unmatched_dataloggers=sorted(k for k in manifest.dataloggers if k.day == day and k not in used_loggers),
            qinertia_projects=sorted(k for k in manifest.qinertia_projects if k.day == day),
            skipped=skipped + (daily.skipped if daily else []),
        )
    return out


@dataclass(frozen=True)
class RunTiming:
    photos: list[PhotoTime]
    residuals_s: list[float]      # FrameID self-check: logged minus computed PC time
    verified: bool


@dataclass(frozen=True)
class DayTiming:
    runs: dict[RunId, dict[str, RunTiming]]
    log_delay_s: float | None     # typical camera processing delay (median residual)
    residual_count: int


def _residuals(rd: RunData, seq: PhotoSequence, day: DayData, cfg: Config) -> list[float]:
    if rd.sbg and rd.pulse_plan and day.clock and rd.sbg.utc_table:
        return frame_line_residuals(rd.frame_lines, seq, rd.sbg, rd.pulse_plan,
                                    day.clock, cfg.expected_step_mm)
    return []


def time_day(day: DayData, cfg: Config) -> DayTiming:
    """Photo times for every run of a day, with the FrameID self-check.

    The camera log writes a photo's line a steady ~0.4 s after the photo is taken
    (processing delay). So each run's lines are compared with the DAY'S typical
    delay, not with zero: a run whose lines differ from it by more than
    frame_log_tolerance_s has the wrong pulse pairing and is marked unverified.
    """
    import statistics

    per_view: dict[tuple[RunId, str], list[float]] = {}
    for rd in day.runs.values():
        for view, seq in rd.photos.items():
            if seq is not None:
                per_view[(rd.run, view)] = _residuals(rd, seq, day, cfg)
    everything = [r for rs in per_view.values() for r in rs]
    delay = statistics.median(everything) if everything else None
    tol = cfg.thresholds.frame_log_tolerance_s
    runs: dict[RunId, dict[str, RunTiming]] = {}
    for rd in day.runs.values():
        out: dict[str, RunTiming] = {}
        for view, seq in rd.photos.items():
            if seq is None:
                continue
            res = per_view.get((rd.run, view), [])
            verified = delay is None or all(abs(r - delay) <= tol for r in res)
            photos = time_photos(seq, rd.sbg, rd.pulse_plan, day.clock, cfg.tz, cfg.expected_step_mm,
                                 rd.camera_start_out, verified, cfg.thresholds.stop_s)
            out[view] = RunTiming(photos, res, verified)
        runs[rd.run] = out
    return DayTiming(runs, delay, len(everything))
