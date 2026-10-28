"""Where QCDATA's own files live (config.yaml, qcdata_state.json).

Beside QCDATA.exe when packaged; the project folder when run from source. If
that folder can't be written (e.g. Program Files), %APPDATA%\\QCDATA is used for
the state file (Phase 5)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ENV_CONFIG = "QCDATA_CONFIG"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def config_path(flag: str | None = None) -> Path:
    """Precedence: --config flag, then QCDATA_CONFIG, then config.yaml beside the app."""
    if flag:
        return Path(flag)
    env = os.environ.get(ENV_CONFIG)
    if env:
        return Path(env)
    return app_dir() / "config.yaml"
