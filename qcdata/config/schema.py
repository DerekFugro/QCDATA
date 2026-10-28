"""config.yaml: defaults, loading, and validation.

Every threshold the checks use lives here with its documented default. Unknown
keys and wrong types are rejected with a message that names the key.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

# C12 (sample-photo receipts) was removed: only photos in the root Images
# folder matter (confirmed by Derek). The ID is not reused.
CHECK_IDS = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11",
             "C13", "C14", "C15", "C16", "C17")

DEFAULTS: dict[str, Any] = {
    "data_drives": ["F:", "G:"],
    "folders": {"images": "Images", "gocator": "GoCatorData", "sbg": "SBGData"},
    "pc_names": ["ARAN01-SERVER", "ARANSW1-SERVER"],
    "local_timezone": "America/New_York",
    "tai_minus_utc_s": 37,
    "sbg_match_tolerance_s": 2,
    "expected_step_mm": 750,
    "partial_copy_threshold": 0.5,
    "max_findings_per_check": 500,
    "checks": {cid: True for cid in CHECK_IDS},
    "thresholds": {
        "c6_warn_m": 3.0,              # tail shortfall (photo count x 0.75 m vs recorded end)
        "c6_fail_m": 8.0,
        "c10_max_abs_diff": 25,        # laser L/R row-count difference allowed...
        "c10_max_pct_diff": 1.0,       # ...or this percent, whichever is larger
        "laser_short_pulses": 2,       # pulses outside laser data before WARN (~1.5 m)
        "min_pulse_gap_s": 0.13,       # a pulse closer than this to the previous gets no photo
        "normal_end_short": 2,         # photos short at the end that are normal
        "stop_s": 5.0,                 # pulse gap counted as a stop
        "clock_drift_note_s": 2.0,     # PC-vs-GPS drift within a day worth highlighting
        "frame_log_tolerance_s": 0.1,  # FrameID self-check: allowed deviation from the day's typical log delay
    },
}

# C13 (database) is off until Phase 6.
DEFAULTS["checks"]["C13"] = False

_DRIVE_RE = re.compile(r"^[A-Za-z]:$")


class ConfigError(ValueError):
    """config.yaml is unreadable or invalid. The message names the key."""


@dataclass(frozen=True)
class Thresholds:
    c6_warn_m: float
    c6_fail_m: float
    c10_max_abs_diff: int
    c10_max_pct_diff: float
    laser_short_pulses: int
    min_pulse_gap_s: float
    normal_end_short: int
    stop_s: float
    clock_drift_note_s: float
    frame_log_tolerance_s: float


@dataclass(frozen=True)
class Config:
    data_drives: tuple[str, ...]
    folder_images: str
    folder_gocator: str
    folder_sbg: str
    pc_names: tuple[str, ...]
    local_timezone: str
    tai_minus_utc_s: float
    sbg_match_tolerance_s: int
    expected_step_mm: int
    partial_copy_threshold: float
    max_findings_per_check: int
    checks: dict[str, bool]
    thresholds: Thresholds

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.local_timezone)

    def enabled(self, check_id: str) -> bool:
        return self.checks.get(check_id, False)


def _merge(defaults: dict, given: dict, path: str) -> dict:
    out = copy.deepcopy(defaults)
    for key, value in given.items():
        where = f"{path}{key}"
        if key not in defaults:
            raise ConfigError(f"Unknown setting '{where}' in config.yaml.")
        want = defaults[key]
        if isinstance(want, dict):
            if not isinstance(value, dict):
                raise ConfigError(f"'{where}' must be a section (key: value lines).")
            out[key] = _merge(want, value, where + ".")
        elif isinstance(want, bool):
            if not isinstance(value, bool):
                raise ConfigError(f"'{where}' must be true or false.")
            out[key] = value
        elif isinstance(want, float):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ConfigError(f"'{where}' must be a number.")
            out[key] = float(value)
        elif isinstance(want, int):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ConfigError(f"'{where}' must be a whole number.")
            out[key] = value
        elif isinstance(want, str):
            if not isinstance(value, str) or not value.strip():
                raise ConfigError(f"'{where}' must be text.")
            out[key] = value.strip()
        elif isinstance(want, list):
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ConfigError(f"'{where}' must be a list of text values.")
            out[key] = list(value)
    return out


def _validate(d: dict) -> Config:
    for drive in d["data_drives"]:
        if not _DRIVE_RE.match(drive):
            raise ConfigError(f"'data_drives' entry '{drive}' must look like 'F:'.")
    try:
        ZoneInfo(d["local_timezone"])
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ConfigError(f"'local_timezone' '{d['local_timezone']}' is not a known time zone.") from exc
    t = d["thresholds"]
    for key, value in t.items():
        if value < 0:
            raise ConfigError(f"'thresholds.{key}' must not be negative.")
    if t["c6_fail_m"] < t["c6_warn_m"]:
        raise ConfigError("'thresholds.c6_fail_m' must be at least 'thresholds.c6_warn_m'.")
    if not 0 < d["partial_copy_threshold"] <= 1:
        raise ConfigError("'partial_copy_threshold' must be between 0 and 1.")
    for key in ("expected_step_mm", "max_findings_per_check"):
        if d[key] <= 0:
            raise ConfigError(f"'{key}' must be greater than zero.")
    return Config(
        data_drives=tuple(x.upper() for x in d["data_drives"]),
        folder_images=d["folders"]["images"],
        folder_gocator=d["folders"]["gocator"],
        folder_sbg=d["folders"]["sbg"],
        pc_names=tuple(d["pc_names"]),
        local_timezone=d["local_timezone"],
        tai_minus_utc_s=float(d["tai_minus_utc_s"]),
        sbg_match_tolerance_s=d["sbg_match_tolerance_s"],
        expected_step_mm=d["expected_step_mm"],
        partial_copy_threshold=d["partial_copy_threshold"],
        max_findings_per_check=d["max_findings_per_check"],
        checks=dict(d["checks"]),
        thresholds=Thresholds(**t),
    )


def default_config() -> Config:
    return _validate(copy.deepcopy(DEFAULTS))


def load_config(path: Path | None) -> Config:
    """Load config.yaml, or defaults if `path` is None or the file doesn't exist."""
    if path is None or not Path(path).exists():
        return default_config()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            given = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"config.yaml could not be read: {exc}") from exc
    if not isinstance(given, dict):
        raise ConfigError("config.yaml must contain 'key: value' settings.")
    return _validate(_merge(DEFAULTS, given, ""))
