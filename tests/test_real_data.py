"""Phase 2 checkpoints against the real sample data (skipped without it)."""

from __future__ import annotations

from collections import Counter

import pytest

from qcdata.core.discovery import discover
from qcdata.core.loader import load_days, time_day
from qcdata.core.model import RunId
from qcdata.core.parsers.export_log import collect_runs, parse_run_list
from qcdata.core.parsers.qc_video import parse_qc_video

R = RunId


def test_reference_counts_20261017(ref_days, ref_manifest):
    d = ref_days["20261017"]
    exported = {r for r, rd in d.runs.items() if rd.export_rows}
    assert len(exported) == 28
    assert len(d.daily.run_rows) == 28
    assert len({m.run for m in d.status if m.run}) == 30
    assert len([r for r in ref_manifest.image_runs if r.day == "20261017"]) == 30
    assert len([r for r in ref_manifest.gocator_runs if r.day == "20261017"]) == 30


def test_counts_20261016(ref_days, ref_manifest):
    d = ref_days["20261016"]
    assert len({r for r, rd in d.runs.items() if rd.export_rows}) == 48
    assert len(d.daily.run_rows) == 48
    assert len([r for r in ref_manifest.image_runs if r.day == "20261016"]) == 4
    # The 4 runs with photos are exactly the Daily's 4 "C" runs; the other 44 are "X".
    c_runs = {r.run for r in d.daily.run_rows if r.status == "C"}
    assert c_runs == {r for r in ref_manifest.image_runs if r.day == "20261016"}
    assert Counter(r.status for r in d.daily.run_rows) == {"C": 4, "X": 44}


def test_step_is_750_everywhere(ref_days):
    for d in ref_days.values():
        for rd in d.runs.values():
            for seq in rd.photos.values():
                if seq is not None and seq.count >= 2:
                    assert seq.step_mm == 750, (rd.run, seq.view)


def test_daily_20261017(ref_days):
    d = ref_days["20261017"].daily
    assert Counter(r.status for r in d.run_rows) == {"C": 25, "X": 3}
    assert {str(r.run) for r in d.run_rows if r.status == "X"} == {
        "20261017.142650", "20261017.160558", "20261017.161445"}
    assert d.meta["acs_version"] == "2.6.5.774" and d.meta["time_in_motion"] == "2h 0m 24s"
    assert d.skipped == []


def test_sbg_matching_20261017(ref_days):
    d = ref_days["20261017"]
    photo_runs = [rd for rd in d.runs.values() if rd.has_image_dir]
    assert len(photo_runs) == 30 and all(rd.sbg for rd in photo_runs)
    assert d.runs[R("20261017.154208")].sbg.folder_run == R("20261017.154209")
    assert d.runs[R("20261017.154927")].sbg.folder_run == R("20261017.154928")
    assert [str(x) for x in d.unmatched_dataloggers] == ["20261017.151624", "20261017.163727"]


def test_pulses_plus_one_rule_20261017(ref_days):
    d = ref_days["20261017"]
    for rd in d.runs.values():
        if rd.sbg:
            for seq in rd.photos.values():
                assert seq.count == len(rd.pulse_plan.photo_pulses_us) + 1, (rd.run, seq.view)
    assert d.runs[R("20261017.154422")].pulse_plan.no_photo_pulses == (1,)
    assert sum(len(rd.pulse_plan.no_photo_pulses) for rd in d.runs.values() if rd.pulse_plan) == 1


def test_counter_rollover_170358(ref_days):
    sbg = ref_days["20261017"].runs[R("20261017.170358")].sbg
    assert sbg.rollovers == 1
    assert all(b > a for a, b in zip(sbg.pulses_us, sbg.pulses_us[1:]))
    assert sbg.utc_table[0][0] <= sbg.pulses_us[0] and sbg.pulses_us[-1] <= sbg.utc_table[-1][0]


def test_pc_offset_from_sbg_log(ref_days):
    d = ref_days["20261017"]
    assert d.clock.source == "sbg_log"
    assert d.offsets[0].delta_s == pytest.approx(3651.555, abs=0.001)
    assert d.offsets[0].display_minus_utc_s == pytest.approx(-14348.445, abs=0.001)


def test_frameid_selfcheck_20261017(ref_days, cfg):
    t = time_day(ref_days["20261017"], cfg)
    assert t.residual_count == 56
    assert 0.3 < t.log_delay_s < 0.5                       # steady camera processing delay
    for run, views in t.runs.items():
        for view, rt in views.items():
            assert rt.verified, (run, view, rt.residuals_s)


def test_pc_offset_frameid_fallback(ref_manifest, cfg):
    """With SBG.log removed, the FrameID lines give the same clock (within 0.2 s
    once the steady camera delay is allowed for)."""
    m = ref_manifest
    no_sbg = [lf for lf in m.acs_logs if lf.kind.lower() != "sbg"]
    m2 = type(m)(**{**m.__dict__, "acs_logs": no_sbg})
    day = load_days(m2, ["20261017"], cfg, read_lasers=False)["20261017"]
    assert day.clock.source == "frame_lines"
    ref = load_days(m, ["20261017"], cfg, read_lasers=False)["20261017"]
    utc = ref.offsets[len(ref.offsets) // 2].hw_unix
    fallback = day.clock.display_minus_utc(utc)
    sbg = ref.clock.display_minus_utc(utc)
    delay = time_day(ref, cfg).log_delay_s
    assert abs(fallback - sbg - delay) < 0.2


def test_lasers_20261017(ref_days, cfg):
    d = ref_days["20261017"]
    for rd in d.runs.values():
        if rd.has_gocator_dir:
            for side in "LR":
                lf = rd.lasers[side]
                assert lf.state != "missing", (rd.run, side)
                assert lf.missing_frames == 0, (rd.run, side)
    assert {rd.lasers["L"].state for r, rd in d.runs.items() if str(r) == "20261017.160558"} == {"empty"}
    assert d.runs[R("20261017.160558")].lasers["R"].state == "empty"


def test_laser_start_end_vs_pulses_20261017(ref_days, cfg):
    """Pulses before the first / after the last laser row, per side. Only 154208
    starts late (one pulse, both sides); none stop early."""
    from qcdata.core.parsers.sbg import UtcConverter
    d = ref_days["20261017"]
    late = {}
    for rd in d.runs.values():
        if not (rd.sbg and rd.lasers and len(rd.pulse_plan.photo_pulses_us) >= 20):
            continue
        conv = UtcConverter(rd.sbg.utc_table)
        utc = [conv.to_utc(p) for p in rd.pulse_plan.photo_pulses_us]
        for side, lf in rd.lasers.items():
            if lf.state != "present":
                continue
            first = lf.first_ptp_us / 1e6 - cfg.tai_minus_utc_s
            last = lf.last_ptp_us / 1e6 - cfg.tai_minus_utc_s
            before = sum(1 for u in utc if u < first)
            after = sum(1 for u in utc if u > last)
            assert after == 0, (rd.run, side)
            if before:
                late[(str(rd.run), side)] = before
    assert late == {("20261017.154208", "L"): 1, ("20261017.154208", "R"): 1}


def test_batch1_export_collection(sample_root, cfg):
    m = discover(sample_root / "Zipfiles" / "Batch1", cfg)
    runs = collect_runs([parse_run_list(p) for p in m.run_lists])
    assert sorted(runs) == ["20261009", "20261010", "20261014", "20261016", "20261017"]
    assert "20261015" not in runs
    # Two exports that day: 09:39 (first 2 runs) and 18:07 (all 48 again). Union = 48.
    assert len(runs["20261016"]) == 48
    morning = [p for p in m.run_lists if "20261016093917" in p.name]
    assert morning and {r.run for r in parse_run_list(morning[0]).rows} <= set(runs["20261016"])
    assert len(m.export_process_logs) == 4      # ExportLogs\*_export_log.csv are not run lists


def test_qc_video_parses_everywhere(sample_root):
    found = list(sample_root.rglob("QC_Video.csv"))
    assert found
    total = 0
    for p in found:
        rows, skipped = parse_qc_video(p)
        assert skipped == [], p
        total += len(rows)
    notes = [r for p in found for r in parse_qc_video(p)[0] if r.note]
    assert total > 0 and notes and notes[0].note.startswith("File Deleted")
