"""Find every part of a collection drive (F:\\, G:\\) or a copied folder of the
same shape. Directory listings only: nothing here reads file contents except the
first few lines of candidate export files, to tell a run list from a process log.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from qcdata.config.schema import Config
from qcdata.core.model import RunId

DAY_RE = re.compile(r"^\d{8}$")
YYMMDD_RE = re.compile(r"^\d{6}$")
DATALOGGER_RE = re.compile(r"^(\d{8}\.\d{6})\s+DataLogger$", re.IGNORECASE)
QINERTIA_RE = re.compile(r"^(\d{8}\.\d{6})_\d{4}$")
DAILY_RE = re.compile(r"^Daily_.+_(\d{8})\.csv$", re.IGNORECASE)
STATUS_RE = re.compile(r"^[^ ]+_StatusMessages_(\d{8})\.csv$", re.IGNORECASE)
SETTINGS_RE = re.compile(r"^[^ ]+_Settings_(\d{8})\.xml$", re.IGNORECASE)
EXPORT_NAME_RE = re.compile(r"_Export_\d{14}.*\.csv$", re.IGNORECASE)


class NotASignoffFolder(Exception):
    """The chosen folder doesn't have the collection-drive shape. The message
    says what is missing, in plain words."""


@dataclass(frozen=True)
class LogFile:
    path: Path
    pc_name: str
    kind: str          # e.g. "SBG", "VideoLogCXP"
    rotation: int      # 0 for ".log", N for ".log.N"


@dataclass
class DayFolder:
    day: str
    path: Path
    daily: Path | None = None
    status_messages: Path | None = None
    settings: Path | None = None
    qc_video: Path | None = None
    log_dirs: list[Path] = field(default_factory=list)          # Logs/<PC>/


@dataclass
class Manifest:
    root: Path
    days: dict[str, DayFolder]
    images_dir: Path | None
    gocator_dir: Path | None
    sbg_dir: Path | None
    image_runs: dict[RunId, Path]
    gocator_runs: dict[RunId, Path]
    dataloggers: dict[RunId, Path]          # keyed by the FOLDER's run id
    qinertia_projects: dict[RunId, Path]
    run_lists: list[Path]                   # export files with a UniqueRun header
    export_process_logs: list[Path]         # export step logs (IDExportLogDetail)
    acs_logs: list[LogFile]
    extra_log_dir: Path | None
    unreadable: list[str] = field(default_factory=list)

    def sbg_day_dirs(self) -> list[str]:
        if not self.sbg_dir:
            return []
        return sorted(e.name for e in _scandir(self.sbg_dir) if e.is_dir() and YYMMDD_RE.match(e.name))


def _scandir(path: Path) -> list[os.DirEntry]:
    try:
        with os.scandir(path) as it:
            return list(it)
    except OSError:
        return []


def _find_child(root: Path, name: str) -> Path | None:
    for e in _scandir(root):
        if e.is_dir() and e.name.lower() == name.lower():
            return Path(e.path)
    return None


def _run_dirs(parent: Path | None) -> dict[RunId, Path]:
    out: dict[RunId, Path] = {}
    if parent is None:
        return out
    for e in _scandir(parent):
        if e.is_dir():
            rid = RunId.parse(e.name)
            if rid and "[" not in e.name:
                out[rid] = Path(e.path)
    return out


def _scan_day(day: str, path: Path) -> DayFolder:
    d = DayFolder(day=day, path=path)
    for e in _scandir(path):
        name = e.name
        if e.is_file():
            if (m := DAILY_RE.match(name)) and (d.daily is None or m.group(1) == day):
                d.daily = Path(e.path)
            elif (m := STATUS_RE.match(name)) and m.group(1) == day:
                d.status_messages = Path(e.path)
            elif (m := SETTINGS_RE.match(name)) and m.group(1) == day:
                d.settings = Path(e.path)
            elif name.lower() == "qc_video.csv":
                d.qc_video = Path(e.path)
        elif e.is_dir():
            # Morning / Mid-Day / Evening sample-photo folders are ignored: only
            # photos in the root Images folder matter (confirmed by Derek).
            if name.lower() == "logs":
                d.log_dirs = [Path(x.path) for x in _scandir(Path(e.path)) if x.is_dir()]
    return d


def classify_export_file(path: Path) -> str:
    """'run_list' (has a UniqueRun header), 'process_log' (export step log), or 'other'."""
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
            for _ in range(12):
                line = fh.readline()
                if not line:
                    break
                head = line.strip().lower()
                if head.startswith("uniquerun,"):
                    return "run_list"
                if head.startswith("idexportlogdetail,"):
                    return "process_log"
    except OSError:
        return "other"
    return "other"


def _log_name_re(pc_names: tuple[str, ...]) -> re.Pattern:
    names = "|".join(re.escape(n) for n in pc_names)
    return re.compile(rf"^(?P<pc>{names})-(?P<kind>[A-Za-z0-9]+)\.log(?:\.(?P<rot>\d+))?$", re.IGNORECASE)


def _walk_files(root: Path, max_depth: int):
    stack = [(root, 0)]
    while stack:
        folder, depth = stack.pop()
        for e in _scandir(folder):
            if e.is_file():
                yield Path(e.path)
            elif e.is_dir() and depth < max_depth and not e.name.startswith(("$", "System Volume")):
                stack.append((Path(e.path), depth + 1))


def discover(root: Path, cfg: Config, extra_log_dir: Path | None = None) -> Manifest:
    root = Path(root)
    if not root.exists() or not root.is_dir():
        raise NotASignoffFolder(f"The folder {root} doesn't exist or can't be opened.")

    entries = _scandir(root)
    days = {e.name: _scan_day(e.name, Path(e.path)) for e in entries if e.is_dir() and DAY_RE.match(e.name)}
    images = _find_child(root, cfg.folder_images)
    gocator = _find_child(root, cfg.folder_gocator)
    sbg = _find_child(root, cfg.folder_sbg)

    if not days and not (images or gocator or sbg):
        raise NotASignoffFolder(
            f"{root} doesn't look like a collection drive: no day folders (like 20261017) "
            f"and no {cfg.folder_images}, {cfg.folder_gocator} or {cfg.folder_sbg} folder."
        )
    if not (images or gocator or sbg):
        raise NotASignoffFolder(
            f"{root} has day folders but no {cfg.folder_images}, {cfg.folder_gocator} "
            f"or {cfg.folder_sbg} folder, so there is no collected data to check."
        )

    # DataLogger folders and Qinertia projects
    dataloggers: dict[RunId, Path] = {}
    qinertia: dict[RunId, Path] = {}
    if sbg:
        for e in _scandir(sbg):
            if not e.is_dir():
                continue
            if YYMMDD_RE.match(e.name):
                for sub in _scandir(Path(e.path)):
                    m = DATALOGGER_RE.match(sub.name)
                    if sub.is_dir() and m:
                        dataloggers[RunId(m.group(1))] = Path(sub.path)
            elif m := QINERTIA_RE.match(e.name):
                qinertia[RunId(m.group(1))] = Path(e.path)

    # Export files: day folders, root ExportBakFiles / ExportLogs, extra log folder
    candidates: list[Path] = []
    for d in days.values():
        candidates += [Path(e.path) for e in _scandir(d.path) if e.is_file() and EXPORT_NAME_RE.search(e.name)]
    for name in ("ExportBakFiles", "ExportLogs"):
        sub = _find_child(root, name)
        if sub:
            candidates += [Path(e.path) for e in _scandir(sub) if e.is_file() and EXPORT_NAME_RE.search(e.name)]
    if extra_log_dir:
        candidates += [p for p in _walk_files(Path(extra_log_dir), 4) if EXPORT_NAME_RE.search(p.name)]
    run_lists, process_logs = [], []
    for p in candidates:
        kind = classify_export_file(p)
        (run_lists if kind == "run_list" else process_logs if kind == "process_log" else []).append(p)

    # ACS logs: every day's Logs/<PC>/ plus the extra log folder; de-duplicate by name + size
    name_re = _log_name_re(cfg.pc_names)
    seen: set[tuple[str, int]] = set()
    logs: list[LogFile] = []
    log_paths: list[Path] = []
    for d in days.values():
        for ld in d.log_dirs:
            log_paths += [Path(e.path) for e in _scandir(ld) if e.is_file()]
    if extra_log_dir:
        log_paths += list(_walk_files(Path(extra_log_dir), 4))
    for p in log_paths:
        m = name_re.match(p.name)
        if not m:
            continue
        try:
            key = (p.name.lower(), p.stat().st_size)
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        logs.append(LogFile(p, m.group("pc"), m.group("kind"), int(m.group("rot") or 0)))

    return Manifest(
        root=root, days=dict(sorted(days.items())), images_dir=images, gocator_dir=gocator,
        sbg_dir=sbg, image_runs=_run_dirs(images), gocator_runs=_run_dirs(gocator),
        dataloggers=dataloggers, qinertia_projects=qinertia, run_lists=sorted(run_lists),
        export_process_logs=sorted(process_logs), acs_logs=sorted(logs, key=lambda l: str(l.path)),
        extra_log_dir=Path(extra_log_dir) if extra_log_dir else None,
    )


def match_datalogger(run: RunId, dataloggers: dict[RunId, Path], tolerance_s: int) -> RunId | None:
    """The DataLogger folder for a run: exact name first, else the nearest within tolerance."""
    if run in dataloggers:
        return run
    near = [k for k in dataloggers if k.within(run, tolerance_s)]
    if not near:
        return None
    return min(near, key=lambda k: abs(k.seconds_of_day - run.seconds_of_day))
