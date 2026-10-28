"""Each check triggered on purpose on a synthetic drive, plus the engine's rules:
explained-by-the-crew, partial-copy guard, crash isolation, caps, determinism."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from qcdata.core import engine
from qcdata.core.checks import REGISTRY
from qcdata.core.engine import by_section
from qcdata.core.model import Severity
from qcdata.core.report_data import build
from tests.fixtures import FakeDay, FakeRun, build as build_drive

DAY = "20261017"


def check(tmp_path: Path, runs, cfg, **day_kw):
    root = build_drive(tmp_path / "F", [FakeDay(runs=runs, **day_kw)])
    res = engine.run(root, cfg, days=[DAY])
    return res, res.days[DAY]


def crew(r, cid=None):
    return [f for f in by_section(r)["crew"] if cid is None or f.check_id == cid]


def tech(r, cid=None):
    return [f for f in by_section(r)["technical"] if cid is None or f.check_id == cid]


def run_id(i: int) -> str:
    return f"{DAY}.15{i:02d}00"


# ------------------------------------------------------------- clean day
def test_clean_synthetic_day_passes(tmp_path, cfg):
    _, r = check(tmp_path, [FakeRun(run_id(1)), FakeRun(run_id(2))], cfg, logs=True)
    assert r.verdict is Severity.PASS, [f.message_plain for f in crew(r)]
    assert r.stats["runs_checked"] == 2


# ------------------------------------------------------------- C1 / C2
def test_c1_daily_missing_fails_and_export_missing_warns(tmp_path, cfg):
    _, r = check(tmp_path, [FakeRun(run_id(1))], cfg, daily=False, export_in_day_folder=False)
    msgs = [(f.severity, f.message_plain) for f in crew(r, "C1")]
    assert any(s is Severity.FAIL and "Daily file" in m for s, m in msgs)
    assert any(s is Severity.WARN and "export log" in m for s, m in msgs)


def test_c2_lists_differ(tmp_path, cfg):
    _, r = check(tmp_path, [FakeRun(run_id(1)), FakeRun(run_id(2), in_export=False)], cfg)
    [f] = crew(r, "C2")
    assert f.severity is Severity.WARN and f.details["daily_only"] == [run_id(2)]


# ------------------------------------------------------------- C3 + partial-copy guard + statuses
def test_c3_missing_payload_fails(tmp_path, cfg):
    _, r = check(tmp_path, [FakeRun(run_id(1)), FakeRun(run_id(2)), FakeRun(run_id(3), images=False)], cfg)
    [f] = crew(r, "C3")
    assert f.severity is Severity.FAIL and "no photos" in f.message_plain


def test_partial_copy_guard_emits_one_finding(tmp_path, cfg):
    runs = [FakeRun(f"{DAY}.{10 + i // 6:02d}{(i % 6) * 10:02d}00", images=i < 4,
                    laser_rows=50 if i < 4 else None, with_sbg=i < 4) for i in range(48)]
    _, r = check(tmp_path, runs, cfg)
    c3 = crew(r, "C3")
    assert len(c3) == 1 and c3[0].severity is Severity.WARN
    assert "44 of 48" in c3[0].message_plain and len(c3[0].details["suppressed_runs"]) == 44


def test_x_status_not_checked_and_v_checked(tmp_path, cfg):
    runs = [FakeRun(run_id(1)), FakeRun(run_id(2), status="X", comment="Delete File - ACS error", images=False),
            FakeRun(run_id(3), status="V", images=False)]
    _, r = check(tmp_path, runs, cfg)
    assert [f.run.value for f in crew(r, "C3")] == [run_id(3)]
    [x] = by_section(r)["explained"]
    assert "deleted by the crew" in x.message_plain and "ACS error" in x.message_plain


def test_c7_runs_without_daily_row_are_info(tmp_path, cfg):
    _, r = check(tmp_path, [FakeRun(run_id(1)), FakeRun(run_id(2), status=None, in_export=False)], cfg, logs=True)
    [f] = tech(r, "C7")
    assert run_id(2) in f.message_plain and r.verdict is Severity.PASS


# ------------------------------------------------------------- C4 / C5 / C6
def test_c4_cameras_differ(tmp_path, cfg):
    _, r = check(tmp_path, [FakeRun(run_id(1), rear_photos=8)], cfg)
    [f] = crew(r, "C4")
    assert f.severity is Severity.FAIL and "ROW 10, Rear 8" in f.message_plain


def test_c5_detects_injected_gap(tmp_path, cfg):
    _, r = check(tmp_path, [FakeRun(run_id(1), drop_photos=(5,))], cfg)
    fs = crew(r, "C5")
    assert {f.subject for f in fs} == {"ROW", "Rear"}
    assert all(f.severity is Severity.FAIL and f.details["missing"] == ["000000003750.jpg"] for f in fs)


def test_c6_short_tail_fails_and_collected_short_is_explained(tmp_path, cfg):
    _, r = check(tmp_path, [FakeRun(run_id(1), end_m=20.0)], cfg)
    assert {f.severity for f in crew(r, "C6")} == {Severity.FAIL}
    _, r = check(tmp_path / "b", [FakeRun(run_id(1), end_m=20.0,
                                          comment="Other - narrow - Section Collected Short - Dead End")], cfg)
    assert crew(r, "C6") == []
    assert any(f.check_id == "C6" and "Collected Short" in f.message_plain for f in by_section(r)["explained"])


def test_c6_zero_end_is_special_cased(tmp_path, cfg):
    _, r = check(tmp_path, [FakeRun(run_id(1), end_m=0)], cfg)
    fs = crew(r, "C6")
    assert fs and all(f.severity is Severity.WARN and "zero length" in f.message_plain for f in fs)


def test_delete_comment_on_collected_run_is_shown(tmp_path, cfg):
    _, r = check(tmp_path, [FakeRun(run_id(1), end_m=0, comment="Delete File - due to ACS errors")], cfg)
    f = crew(r, "C6")[0]
    assert "Delete File - due to ACS errors" in f.message_plain and "marked deleted" in f.what_to_do


# ------------------------------------------------------------- C10 lasers
def test_c10_missing_empty_and_rowcount(tmp_path, cfg):
    runs = [FakeRun(run_id(1), laser_sides="L"),
            FakeRun(run_id(2), laser_rows_by_side={"R": 0}),
            FakeRun(run_id(3), laser_rows=200, laser_rows_by_side={"R": 100})]
    _, r = check(tmp_path, runs, cfg)
    by = {(f.run.value, f.subject): f for f in crew(r, "C10")}
    assert by[(run_id(1), "right laser")].severity is Severity.FAIL
    assert "empty" in by[(run_id(2), "right laser")].message_plain
    assert "very different lengths" in by[(run_id(3), "lasers")].message_plain


def test_laser_short_counts_pulses_per_side(tmp_path, cfg):
    runs = [FakeRun(run_id(1), photos=20, laser_start_pulse={"R": 5}),     # right starts 5 pulses late
            FakeRun(run_id(2), photos=20, laser_start_pulse={"L": 1, "R": 1})]  # 1 pulse late = normal
    _, r = check(tmp_path, runs, cfg)
    [f] = crew(r, "C10")
    assert f.run.value == run_id(1) and f.subject == "right laser" and "starts 5 camera pulse" in f.message_plain
    notes = [f for f in tech(r, "C10") if f.run.value == run_id(2)]
    assert len(notes) == 2 and all("normal allowance" in f.message_plain for f in notes)


# ------------------------------------------------------------- C11
def test_c11_missing_parts(tmp_path, cfg):
    _, r = check(tmp_path, [FakeRun(run_id(1), with_sbg=False)], cfg, qinertia=False)
    msgs = " | ".join(f.message_plain for f in crew(r, "C11"))
    assert "SBG data folder" in msgs and "Qinertia" in msgs and "camera log" in msgs
    assert "DataLogger folder is missing" in msgs


# ------------------------------------------------------------- C14 QC_Video
def test_c14_agrees_and_detects_disagreement(tmp_path, cfg):
    runs = [FakeRun(run_id(1)),                       # fine; QC_Video wrongly lists it
            FakeRun(run_id(2), end_m=20.0),           # real tail loss; QC_Video misses it
            FakeRun(run_id(3), end_m=20.0)]           # real tail loss; QC_Video lists it correctly
    rows = [f"[{run_id(1)}],Image missing,ROW,000000007500.JPG,000000020000.JPG,0.0075,0.02,17",
            f"[{run_id(3)}],Image missing,ROW,000000007500.JPG,000000020000.JPG,0.0075,0.02,17",
            f"[{run_id(3)}],Image missing,Rear,000000007500.JPG,000000020000.JPG,0.0075,0.02,17"]
    _, r = check(tmp_path, runs, cfg, qc_video_rows=rows)
    bad = {(f.run.value, f.subject) for f in crew(r, "C14")}
    assert bad == {(run_id(1), "ROW"), (run_id(2), "ROW"), (run_id(2), "Rear")}
    summary = next(f for f in tech(r, "C14") if "agreed" in f.details)
    assert summary.details["agreed"] == 3 and summary.details["compared"] == 6


# ------------------------------------------------------------- C15 pulses
@pytest.mark.parametrize("pulses,expect", [(8, "extra"), (10, "normal"), (13, "short")])
def test_c15_photo_pulse_rules(tmp_path, cfg, pulses, expect):
    _, r = check(tmp_path, [FakeRun(run_id(1), photos=10, pulses=pulses)], cfg, logs=True)
    c15 = crew(r, "C15")
    if expect == "extra":
        assert c15 and all(f.severity is Severity.FAIL and "more photo" in f.message_plain for f in c15)
    elif expect == "normal":
        assert c15 == [] and any("normal, the cameras stop" in f.message_plain for f in tech(r, "C15"))
    else:
        assert c15 and all(f.severity is Severity.WARN and "4 photo(s) missing at the end" in f.message_plain
                           for f in c15)


def test_c15_start_short_warns(tmp_path, cfg):
    _, r = check(tmp_path, [FakeRun(run_id(1), photos=10, pulses=12, camera_start_after_pulse=2)], cfg, logs=True)
    fs = crew(r, "C15")
    assert fs and all("weren't ready at the start" in f.message_plain for f in fs)


def test_c15_no_photo_pulse_is_a_note(tmp_path, cfg):
    _, r = check(tmp_path, [FakeRun(run_id(1), photos=10, extra_pulse_after=4)], cfg, logs=True)
    assert crew(r, "C15") == []
    assert any("less than 0.13 s" in f.message_plain for f in tech(r, "C15"))


# ------------------------------------------------------------- engine rules
def test_crashing_check_becomes_one_fail_and_others_run(tmp_path, cfg, monkeypatch):
    c4 = next(c for c in REGISTRY if c.id == "C4")
    monkeypatch.setattr(c4, "run", lambda ctx: 1 / 0)
    _, r = check(tmp_path, [FakeRun(run_id(1), drop_photos=(3,))], cfg)
    [boom] = crew(r, "C4")
    assert boom.severity is Severity.FAIL and "couldn't finish" in boom.message_plain
    assert crew(r, "C5"), "other checks must still run"


def test_findings_are_capped(tmp_path, cfg):
    small = replace(cfg, max_findings_per_check=2)
    runs = [FakeRun(run_id(i), drop_photos=(3,)) for i in range(1, 4)]   # 6 C5 findings
    _, r = check(tmp_path, runs, small)
    c5 = crew(r, "C5")
    assert len(c5) == 3 and c5[-1].message_plain == "…and 4 more like this."


def test_disabled_check_does_not_run(tmp_path, cfg):
    off = replace(cfg, checks={**cfg.checks, "C5": False})
    _, r = check(tmp_path, [FakeRun(run_id(1), drop_photos=(3,))], off)
    assert crew(r, "C5") == []


def test_report_data_is_deterministic(tmp_path, cfg):
    root = build_drive(tmp_path / "F", [FakeDay(runs=[FakeRun(run_id(1), drop_photos=(3,)), FakeRun(run_id(2))],
                                                logs=True)])
    a = build(engine.run(root, cfg, days=[DAY]))
    b = build(engine.run(root, cfg, days=[DAY]))
    a.pop("generated_at"), b.pop("generated_at")
    assert a == b


def test_newest_day_default(tmp_path, cfg):
    root = build_drive(tmp_path / "F", [FakeDay(day="20261016", runs=[FakeRun("20261016.150000")]),
                                        FakeDay(day=DAY, runs=[FakeRun(run_id(1))])])
    res = engine.run(root, cfg)
    assert list(res.days) == [DAY]
    assert list(engine.run(root, cfg, days=["20261016", DAY]).days) == ["20261016", DAY]
