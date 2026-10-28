"""Discovery, pulse/photo pairing and the loader, on synthetic drives."""

from __future__ import annotations

import builtins
import hashlib
from pathlib import Path

import pytest

from qcdata.core.discovery import NotASignoffFolder, discover, match_datalogger
from qcdata.core.loader import load_days, time_day
from qcdata.core.model import RunId
from qcdata.core.photo_times import plan_pulses
from tests.fixtures import FakeDay, FakeRun, build


def _drive(tmp_path: Path, runs, **kw) -> Path:
    root = build(tmp_path / "F", [FakeDay(runs=runs)], **kw)
    (root / "$RECYCLE.BIN").mkdir()
    (root / "Unrelated stuff").mkdir()
    return root


def test_drive_root_layout_and_ignored_folders(tmp_path, cfg):
    root = _drive(tmp_path, [FakeRun("20261017.150000"), FakeRun("20261017.151000")])
    m = discover(root, cfg)
    assert list(m.days) == ["20261017"]
    assert len(m.image_runs) == len(m.gocator_runs) == len(m.dataloggers) == 2
    assert len(m.run_lists) == 1


def test_folder_names_matched_ignoring_case(tmp_path, cfg):
    root = build(tmp_path / "G", [FakeDay(runs=[FakeRun("20261017.150000")])],
                 payload_names=("images", "GOCATORDATA", "sbgdata"))
    m = discover(root, cfg)
    assert m.images_dir and m.gocator_dir and m.sbg_dir


def test_not_a_signoff_folder_messages(tmp_path, cfg):
    (tmp_path / "empty").mkdir()
    with pytest.raises(NotASignoffFolder, match="no day folders"):
        discover(tmp_path / "empty", cfg)
    (tmp_path / "daysonly" / "20261017").mkdir(parents=True)
    with pytest.raises(NotASignoffFolder, match="no collected data"):
        discover(tmp_path / "daysonly", cfg)
    with pytest.raises(NotASignoffFolder, match="doesn't exist"):
        discover(tmp_path / "missing", cfg)


def test_export_in_root_bakfiles_and_extra_log_folder(tmp_path, cfg):
    root = build(tmp_path / "F", [FakeDay(runs=[FakeRun("20261017.150000")], export_in_day_folder=False)],
                 export_root_bak=True)
    assert len(discover(root, cfg).run_lists) == 1
    # no export anywhere, then found via the extra log folder
    root2 = build(tmp_path / "F2", [FakeDay(runs=[FakeRun("20261017.150000")], export_in_day_folder=False)])
    assert discover(root2, cfg).run_lists == []
    extra = tmp_path / "copied logs" / "deep"
    extra.mkdir(parents=True)
    (extra / "ARAN01_Export_20261017171030_log.csv").write_text(
        "T\n\nUniqueRun,SectionName,BeginDistanceStamp,EndDistanceStamp,BeginChainage,EndChainage\n"
        "[20261017.150000],300000,0,7.5,0,0.0075\n", encoding="utf-8")
    assert len(discover(root2, cfg, extra_log_dir=tmp_path / "copied logs").run_lists) == 1


def test_sbg_folder_matches_within_2s(cfg):
    loggers = {RunId("20261017.154209"): Path("a"), RunId("20261017.154928"): Path("b")}
    assert match_datalogger(RunId("20261017.154208"), loggers, 2) == RunId("20261017.154209")
    assert match_datalogger(RunId("20261017.154927"), loggers, 2) == RunId("20261017.154928")
    assert match_datalogger(RunId("20261017.154205"), loggers, 2) is None


def test_plan_pulses_drops_pulse_under_min_gap():
    us = [0, 50_000, 500_000, 1_000_000]          # second pulse is 0.05 s after the first
    plan = plan_pulses(us, 0.13)
    assert plan.photo_pulses_us == (0, 500_000, 1_000_000) and plan.no_photo_pulses == (1,)


def test_loader_pairs_photos_with_pulses(tmp_path, cfg):
    runs = [FakeRun("20261017.150000", photos=10),
            FakeRun("20261017.151000", photos=10, extra_pulse_after=3),        # one no-photo pulse
            FakeRun("20261017.152000", photos=10, sbg_name_offset_s=1),        # logger named 1 s late
            FakeRun("20261017.153000", photos=10, rollover_at_pulse=4)]        # counter wraps mid-run
    root = _drive(tmp_path, runs)
    m = discover(root, cfg)
    day = load_days(m, ["20261017"], cfg)["20261017"]
    assert len(day.runs) == 4 and day.unmatched_dataloggers == []
    for rd in day.runs.values():
        assert rd.sbg is not None
        assert rd.photos["ROW"].count == len(rd.pulse_plan.photo_pulses_us) + 1, rd.run
    assert day.runs[RunId("20261017.151000")].pulse_plan.no_photo_pulses == (3,)
    assert day.runs[RunId("20261017.153000")].sbg.rollovers == 1
    p = day.runs[RunId("20261017.153000")].sbg.pulses_us
    assert all(b > a for a, b in zip(p, p[1:]))


def test_photo_times_flags_and_startup_frame(tmp_path, cfg):
    root = _drive(tmp_path, [FakeRun("20261017.151000", photos=6, extra_pulse_after=2)])
    day = load_days(discover(root, cfg), ["20261017"], cfg)["20261017"]
    timing = time_day(day, cfg).runs[RunId("20261017.151000")]["ROW"]
    photos = timing.photos
    assert photos[0].time_source == "startup_frame" and photos[0].pulse_number is None
    assert [p.pulse_number for p in photos[1:]] == [1, 2, 3, 4, 5]
    # the extra pulse sits between photo-pulses 2 and 3, so photo 4 comes right after it
    assert "after_no_photo_pulse" in photos[3].flags
    assert not any("after_no_photo_pulse" in p.flags for i, p in enumerate(photos) if i != 3)
    assert photos[1].gps_utc is not None and photos[1].local_time is not None
    # No SBG.log and no camera log in the fixture: no PC clock, so PC time is blank.
    assert day.clock.source is None and photos[1].pc_time is None


def _snapshot(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_loading_changes_nothing_and_never_opens_a_photo(tmp_path, cfg, monkeypatch):
    root = _drive(tmp_path, [FakeRun("20261017.150000"), FakeRun("20261017.151000", status="X")])
    before = _snapshot(root)
    real_open = builtins.open

    def guarded_open(file, mode="r", *a, **k):
        name = str(file).lower()
        if name.endswith((".jpg", ".jpeg")):
            raise AssertionError(f"photo opened: {file}")
        if any(c in mode for c in "wax+"):
            raise AssertionError(f"opened for writing: {file} ({mode})")
        return real_open(file, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", guarded_open)
    days = load_days(discover(root, cfg), ["20261017"], cfg)
    time_day(days["20261017"], cfg)
    monkeypatch.undo()
    assert _snapshot(root) == before


def test_malformed_lines_are_skipped_not_raised(tmp_path, cfg):
    root = _drive(tmp_path, [FakeRun("20261017.150000")])
    sm = root / "20261017" / "ARAN01_StatusMessages_20261017.csv"
    sm.write_text(sm.read_text() + "nonsense\n\x00\x01,,\n", encoding="utf-8")
    daily = root / "20261017" / "Daily_ARAN01_20261017.csv"
    daily.write_text(daily.read_text() + "weird row,,,\n", encoding="utf-8")
    day = load_days(discover(root, cfg), ["20261017"], cfg)["20261017"]
    assert len(day.skipped) >= 2
