"""Phase 3 verdicts on the real sample data (skipped without it)."""

from __future__ import annotations

from collections import Counter

import pytest

from qcdata.core import engine
from qcdata.core.discovery import discover
from qcdata.core.engine import available_days, by_section
from qcdata.core.inventory import records
from qcdata.core.model import Severity


@pytest.fixture(scope="module")
def ref(sample_root, cfg):
    return engine.run(sample_root / "17thAnd16th", cfg, days=["20261016", "20261017"])


def _text(fs):
    return " | ".join(f.message_plain for f in fs)


def test_reference_day_verdict(ref):
    r = ref.days["20261017"]
    s = by_section(r)
    assert r.verdict is Severity.PASS and s["crew"] == []
    assert len(s["explained"]) == 3
    t = _text(s["technical"])
    assert "20261017.141947" in t and "20261017.154142" in t                     # C7
    assert "less than 0.13 s" in t                                               # C15 154422
    assert sum("normal allowance" in f.message_plain for f in s["technical"] if f.check_id == "C10") == 2
    assert "Session 20261017.165541 logged" in t and "no photos lost" in t           # C8 9057
    assert "NoSolution" in t and "UTC−5" in t and "all matched" in t             # C9, C17


def test_20261016_real_findings(ref):
    r = ref.days["20261016"]
    s = by_section(r)
    assert r.verdict is Severity.WARN
    assert Counter(f.check_id for f in s["crew"]) == {"C6": 2, "C10": 2, "C11": 1}
    assert all(f.run is None or f.run.value == "20261016.172652" for f in s["crew"])
    assert all("Delete File - due to ACS errors" in f.message_plain for f in s["crew"] if f.run)
    assert "Qinertia" in _text(f for f in s["crew"] if f.check_id == "C11")
    assert len(s["explained"]) == 44


def test_inventory_one_record_per_photo(ref):
    r = ref.days["20261017"]
    recs = records("20261017", r.timing)
    files = sum(seq.count for rd in r.data.runs.values() for seq in rd.photos.values() if seq)
    assert len(recs) == files == r.stats["photos"]
    assert {x.time_source for x in recs} <= {"pulse", "startup_frame", "unverified", "none"}
    assert all(x.pc_time for x in recs if x.time_source == "pulse")


@pytest.mark.parametrize("folder", ["20261009_New_Reverse_run", "20261009_NeW_Reverse_Run_Tape"])
def test_c14_agrees_with_qcvideo_20261009(sample_root, cfg, folder):
    res = engine.run(sample_root / folder, cfg, days=["20261009"], read_lasers=False)
    r = res.days["20261009"]
    c14 = [f for f in r.findings if f.check_id == "C14"]
    summary = next(f for f in c14 if "agreed" in f.details)
    assert summary.details["agreed"] == summary.details["compared"] > 0
    assert not [f for f in c14 if f.section == "crew"]
    # the real tail losses QC_Video lists are also QCDATA C6 FAILs
    assert any(f.check_id == "C6" and f.severity is Severity.FAIL for f in r.findings)


def test_batch1_partial_copy_guard_and_missing_export(sample_root, cfg):
    m = discover(sample_root / "Zipfiles" / "Batch1", cfg)
    res = engine.run(sample_root / "Zipfiles" / "Batch1", cfg, days=available_days(m), read_lasers=False)
    guarded = {d for d, r in res.days.items()
               if any(f.check_id == "C3" and "partly copied" in f.message_plain for f in r.findings)}
    assert guarded == {"20261014", "20261015", "20261017"}
    oct15 = by_section(res.days["20261015"])["crew"]
    assert any(f.check_id == "C1" and "export log" in f.message_plain for f in oct15)


def test_laser_no_data_during_run_names_ptp(sample_root, cfg):
    res = engine.run(sample_root / "Zipfiles" / "Batch1", cfg, days=["20261015"])
    fs = [f for f in res.days["20261015"].findings if f.check_id == "C10" and "recorded no data" in f.message_plain]
    assert len(fs) == 2 and all("PTP Time is invalid" in f.message_plain for f in fs)
