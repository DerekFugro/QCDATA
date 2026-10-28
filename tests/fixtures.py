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


@dataclass
class FakeDay:
    day: str = "20261017"
    runs: list[FakeRun] = field(default_factory=list)
    daily: bool = True
    export_in_day_folder: bool = True
    acs_version: str = "2.6.5.774"


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

        for r in fd.runs:
            numbers = [k for k in range(1, r.photos + 1) if k not in r.drop_photos]
            for view in ("ROW", "Rear"):
                vdir = images / r.run / view
                vdir.mkdir(parents=True, exist_ok=True)
                for k in numbers:
                    (vdir / f"{k * STEP:012d}.jpg").write_bytes(b"")
            if r.laser_rows is not None:
                for side in "LR":
                    ld = gocator / r.run
                    lines = ["frameIndex,timestamp,ptpTimestamp,encoder,numberOfProfilePoints,x0,z0"]
                    t0 = int((run_utc_start(r.run) - 1.0 + 37) * 1e6)
                    for i in range(r.laser_rows):
                        lines.append(f"{i + 1},{1000 + i},{t0 + i * 100_000},{5000 + 136 * i},424,1.0,2.0")
                    _w(ld / f"{r.run.replace('.', 'T')}{side}.csv", "\n".join(lines) + "\n")
            if r.with_sbg:
                _write_sbg(sbg, r)
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
