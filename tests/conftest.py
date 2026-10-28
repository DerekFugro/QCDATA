"""Shared fixtures. Real-data tests read the sample drive from QCDATA_SAMPLE_ROOT
(default: F:\\001_BuggyData\\001_RawData\\100_Signoff) and SKIP if it isn't there."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from qcdata.config.schema import default_config

DEFAULT_SAMPLE_ROOT = r"F:\001_BuggyData\001_RawData\100_Signoff"


@pytest.fixture(scope="session")
def cfg():
    return default_config()


@pytest.fixture(scope="session")
def sample_root() -> Path:
    root = Path(os.environ.get("QCDATA_SAMPLE_ROOT", DEFAULT_SAMPLE_ROOT))
    if not (root / "17thAnd16th").is_dir():
        pytest.skip(f"sample data not found at {root}")
    return root


@pytest.fixture(scope="session")
def ref_manifest(sample_root, cfg):
    from qcdata.core.discovery import discover
    return discover(sample_root / "17thAnd16th", cfg)


@pytest.fixture(scope="session")
def ref_days(ref_manifest, cfg):
    from qcdata.core.loader import load_days
    return load_days(ref_manifest, ["20261016", "20261017"], cfg)
