"""Build small synthetic collection drives in a temp folder.

Laid out like the real drive root: <YYYYMMDD>\\ day folders plus Images\\,
GoCatorData\\, SBGData\\. Photos are empty files - QCDATA never opens them.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from pathlib import Path

STEP = 750
UTC_BASE = calendar.timegm((2026, 10, 17, 19, 0, 0))   # 15:00 EDT


@dataclass
class FakeRun:
    run: str                       # "20261017.150000"
    status: str = "C"              # Daily status; None = no Daily row
    comment: str = ""
    photos: int = 10               # photos per view
    drop_photos: tuple[int, ...] = ()   # photo numbers to leave out (holes)
    pulses: int | None = None      # default photos - 1
    extra_pulse_after: int | None = None  # add a pulse 0.05 s after this pulse number
    laser_rows: int | None = 50    # None = no laser files
    end_m: float | None = None     # export EndDistanceStamp; default photos*0.75
    in_export: bool = True
    with_sbg: bool = True
    sbg_name_offset_s: int = 0     # DataLogger folder named this many seconds later
    rollover_at_pulse: int | None = None  # make the device counter wrap at this pulse
    images: bool = True            # write Images/<run>/
    rear_photos: int | None = None # Rear count if different from ROW
    laser_sides: str = "LR"        # which laser files to write
    laser_rows_by_side: dict | None = None      # e.g. {"R": 30}
    laser_start_pulse: dict | None = None       # side -> first pulse index the laser covers
    camera_start_after_pulse: int | None = None # camera log StartAcquisition after this pulse index


@dataclass
class FakeDay:
    day: str = "20261017"
    runs: list[FakeRun] = field(default_factory=list)
    daily: bool = True
    export_in_day_folder: bool = True
    acs_version: str = "2.6.5.774"
    logs: bool = False             # write SBG.log (clock) + camera log
    qc_video_rows: list[str] | None = None   # None = no QC_Video.csv
    qinertia: bool = True          # write an SBGData/<day>.120000_0001 project folder


def _w(path: Path, text: str, newline: str = "\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text.replace("\n", newline))
    return path


def _secs(run: str) -> int:
    return int(run[9:11]) * 3600 + int(run[11:13]) * 60 + int(run[13:15])


def run_utc_start(run: str) -> float:
    """True UTC when the fake run's first pulse fires (PC id is local EDT)."""
    day = run[:8]
    midnight_local = calendar.timegm((int(day[:4]), int(day[4:6]), int(day[6:8]), 0, 0, 0)) + 4 * 3600
    return midnight_local + _secs(run) + 2.0


def build(root: Path, days: list[FakeDay], *, payload_names=("Images", "GoCatorData", "SBGData"),
          export_root_bak: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    images, gocator, sbg = (root / n for n in payload_names)
    for fd in days:
        dd = root / fd.day
        dd.mkdir(parents=True, exist_ok=True)
        if fd.qinertia:
            (sbg / f"{fd.day}.120000_0001").mkdir(parents=True, exist_ok=True)
        # Daily
        if fd.daily:
            hdr = ("FILENAME,ARAN,HEADER,Direction,Lane,From,To,Length,CollLength,FunctionalClass,"
                   "Comments,Initials,Status,LatBeg,LongBeg,GPS Mode,Date,,")
            lines = [hdr, "," * 18]
            for r in fd.runs:
                if r.status is None:
                    continue
                lines.append(f"[{r.run}],1700,3000{r.run[-2:]},5,1,0,0.1,0.1,0.1,5-City Primary,"
                             f"{r.comment},SJO,{r.status},,,NoSolution,Sat Oct 17 15:00:00 2026,,")
            lines += [",,,,,,,,,,,,,Averages:,,,", "," * 18, f"ACS Version {fd.acs_version},,",
                      "Daily Report Version 1.0.0.0,,", "Time in motion - 1h 2m 3s,,"]
            _w(dd / f"Daily_ARAN01_{fd.day}.csv", "\n".join(lines) + "\n")
        # Export run list
        rows = ["ARAN01_Export_20261017171030", f"Start Date: {fd.day}", f"End Date: {fd.day}", "",
                "UniqueRun,SectionName,BeginDistanceStamp,EndDistanceStamp,BeginChainage,EndChainage,"]
        for r in fd.runs:
            if r.in_export:
                end = r.end_m if r.end_m is not None else r.photos * STEP / 1000
                rows.append(f"[{r.run}],3000{r.run[-2:]},0,{end},0,{end/1000:.3f},")
        target = (root / "ExportBakFiles") if export_root_bak else dd
        if fd.export_in_day_folder or export_root_bak:
            _w(target / f"ARAN01_Export_{fd.day}171030_log.csv", "\n".join(rows) + "\n")
        # Status messages
        sm = ["FileName,Severity,Message,Module,StatusDate,DistanceStamp,"]
        for r in fd.runs:
            sm.append(f"[{r.run}],Information,Started a collection session: {r.run},Data Manager,"
                      f"10/17/2026 3:00:00 PM,0,")
            sm.append(f"[{r.run}],Information,End of Section in 285 Meters,Mission Management,"
                      f"10/17/2026 3:00:05 PM,,")
        _w(dd / f"ARAN01_StatusMessages_{fd.day}.csv", "\n".join(sm) + "\n")

        if fd.qc_video_rows is not None:
            _w(dd / "QC_Video.csv", "Session Name,Error,View,First File,Last File,Begin Chainage,"
               "End Chainage,Image Count\n" + "".join(x + "\n" for x in fd.qc_video_rows))
        sbg_lines, cam_lines = [], []
        for r in fd.runs:
            if r.images:
                for view in ("ROW", "Rear"):
                    n = r.rear_photos if (view == "Rear" and r.rear_photos is not None) else r.photos
                    numbers = [k for k in range(1, n + 1) if k not in r.drop_photos]
                    vdir = images / r.run / view
                    vdir.mkdir(parents=True, exist_ok=True)
                    for k in numbers:
                        (vdir / f"{k * STEP:012d}.jpg").write_bytes(b"")
            if r.laser_rows is not None:
                n_pulses = r.pulses if r.pulses is not None else r.photos - 1
                for side in r.laser_sides:
                    ld = gocator / r.run
                    ld.mkdir(parents=True, exist_ok=True)
                    rows = (r.laser_rows_by_side or {}).get(side, r.laser_rows)
                    lines = ["frameIndex,timestamp,ptpTimestamp,encoder,numberOfProfilePoints,x0,z0"]
                    start_pulse = (r.laser_start_pulse or {}).get(side)
                    if start_pulse is None:
                        t0 = run_utc_start(r.run) - 1.0
                        span = max(n_pulses * 0.5 + 2.0, 1.0)
                    else:
                        t0 = run_utc_start(r.run) + 0.5 * start_pulse - 0.1
                        span = max((n_pulses - start_pulse) * 0.5 + 2.0, 1.0)
                    step = span / max(rows - 1, 1)
                    for i in range(rows):
                        ptp = int((t0 + i * step + 37) * 1e6)
                        lines.append(f"{i + 1},{1000 + i},{ptp},{5000 + 136 * i},424,1.0,2.0")
                    _w(ld / f"{r.run.replace('.', 'T')}{side}.csv", "\n".join(lines) + "\n")
            if r.with_sbg:
                _write_sbg(sbg, r)
            if fd.logs:
                u0 = run_utc_start(r.run)
                k = r.camera_start_after_pulse
                start_utc = u0 - 0.5 if k is None else u0 + 0.5 * k + 0.1
                n_pulses = r.pulses if r.pulses is not None else r.photos - 1
                # cameras stop after the pulse of the last photo (before any extra pulses)
                stop_utc = u0 + 0.5 * min(n_pulses, r.photos - 1) - 0.25 + 0.5
                for t in (u0 - 2.0, u0 + 0.5 * n_pulses):
                    sbg_lines.append(_sbg_line(t))
                cam_lines += [_cam_line(start_utc - 0.3, "VC2_StartAcquisition in"),
                              _cam_line(start_utc, "VC2_StartAcquisition out"),
                              _cam_line(stop_utc, "VC2_StopAcquisition in")]
        if fd.logs:
            ld = dd / "Logs" / "ARAN01-SERVER"
            _w(ld / "ARAN01-Server-SBG.log", "".join(sorted(sbg_lines)))
            _w(ld / "ARAN01-SERVER-VideoLogCXP.log", "".join(sorted(cam_lines)))
    return root


def _write_sbg(sbg: Path, r: FakeRun) -> None:
    name_secs = _secs(r.run) + r.sbg_name_offset_s
    name = f"{r.run[:9]}{name_secs // 3600:02d}{name_secs % 3600 // 60:02d}{name_secs % 60:02d}"
    folder = sbg / r.run[2:8] / f"{name} DataLogger"
    utc0 = run_utc_start(r.run)
    n_pulses = r.pulses if r.pulses is not None else r.photos - 1
    dev0 = 3_000_000_000
    pulses = [dev0 + int((1.0 + 0.5 * i) * 1e6) for i in range(n_pulses)]
    if r.extra_pulse_after is not None:
        p = pulses[r.extra_pulse_after - 1] + 50_000
        pulses.insert(r.extra_pulse_after, p)
    span = 3 + int(0.5 * max(n_pulses, 1)) + 2
    utc_rows = [(dev0 + int(i * 1e6), utc0 - 1.0 + i) for i in range(span)]
    if r.rollover_at_pulse is not None:
        # shift so the counter passes 2**32 just before that pulse
        shift = 2**32 - pulses[r.rollover_at_pulse] + 10
        pulses = [(p + shift) % 2**32 for p in pulses]
        utc_rows = [((d + shift) % 2**32, u) for d, u in utc_rows]
    ev = ["timestamp\tstatus\ttimeOffset0\ttimeOffset1\ttimeOffset2\ttimeOffset3",
          "(us)\t(na)\t(us)\t(us)\t(us)\t(us)"] + [f"{p:>10d}\t0x0000\t0\t0\t0\t0" for p in pulses]
    _w(folder / "eventOutA.txt", "\n".join(ev) + "\n", "\r\n")
    _w(folder / "eventOutB.txt", "\n".join(ev) + "\n", "\r\n")
    ev_in = ev[:2] + [f"{p + 120:>10d}\t0x0000\t0\t0\t0\t0" for p in pulses]
    _w(folder / "eventInA.txt", "\n".join(ev_in) + "\n", "\r\n")
    ut = ["timestamp\tstatus\tgpsTimeOfWeek\tyear\tmonth\tday\thour\tminute\tsecond\tnanosecond",
          "(us)\t(na)\t(ms)\t(yyyy)\t(mm)\t(dd)\t(hh)\t(mm)\t(s)\t(ns)"]
    import time as _t
    for d, u in utc_rows:
        g = _t.gmtime(u)
        ut.append(f"{d:>10d}\t0x00a7\t0\t{g.tm_year}\t{g.tm_mon}\t{g.tm_mday}\t{g.tm_hour}\t"
                  f"{g.tm_min}\t{g.tm_sec}\t0")
    _w(folder / "utcTime.txt", "\n".join(ut) + "\n", "\r\n")


# Fixture PC clock: the PC shows true local EDT (UTC-4) with no error.
FIXTURE_DISPLAY_MINUS_UTC = -4 * 3600


def _display(utc: float) -> str:
    import datetime as _dt
    t = _dt.datetime(1970, 1, 1) + _dt.timedelta(seconds=utc + FIXTURE_DISPLAY_MINUS_UTC)
    return t


def _sbg_line(utc: float) -> str:
    t = _display(utc)
    return (f"INFO {t.strftime('%Y-%m-%d %H:%M:%S')}.{t.microsecond // 1000:03d} [22] - CallbackUtc, "
            f"TS HWUnix: {int(utc)} (s), TS PCUnix: {int(utc) + (utc % 1):.3f}, Delta TSUnix PC vs HW: "
            f"{utc % 1:.3f} (PC ahead), timeStamp: 1 (HW us), status: 167\n")


def _cam_line(utc: float, body: str) -> str:
    t = _display(utc)
    return f"{t.strftime('%Y-%m-%d %H:%M:%S')},{t.microsecond // 1000:03d} 0x00001aac root - {body}\n"
