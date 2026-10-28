"""Phase 4: the HTML report, the files it adds, and the `qcdata check` command."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from qcdata.cli.main import main
from qcdata.core import engine
from qcdata.core.inventory import COLUMNS
from qcdata.core.paths import OUTPUT_DIR_NAME, WriteGuard
from qcdata.core.report import writer
from qcdata.core.report.render import render_html
from qcdata.core.report_data import build
from tests.fixtures import FakeDay, FakeRun, build as build_drive

DAY = "20261017"
XSS = "<script>alert(1)</script>"


def drive(tmp_path, runs=None, **kw) -> Path:
    runs = runs or [FakeRun("20261017.150000"), FakeRun("20261017.151000")]
    kw.setdefault("logs", True)
    return build_drive(tmp_path / "F", [FakeDay(runs=runs, **kw)])


def snapshot(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def html_for(root, cfg) -> str:
    res = engine.run(root, cfg, days=[DAY])
    return render_html(build(res, datetime(2026, 10, 28, 9, 0)), "images.csv", "findings.json")


# --- the HTML ---------------------------------------------------------------

def test_hostile_text_renders_as_text(tmp_path, cfg):
    root = drive(tmp_path, [FakeRun("20261017.150000", comment=XSS),
                            FakeRun("20261017.151000", status="X", comment=XSS)])
    html = html_for(root, cfg)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script" not in html.lower()


def test_report_is_self_contained(tmp_path, cfg):
    html = html_for(drive(tmp_path), cfg)
    low = html.lower()
    for bad in ("http://", "https://", "<link", "<script", "src=", "@import", "url("):
        assert bad not in low, bad


@pytest.mark.parametrize("kw,word", [
    ({}, "PASS"),
    ({"qinertia": False}, "NEEDS A LOOK"),
])
def test_verdict_spelled_out_not_colour_only(tmp_path, cfg, kw, word):
    html = html_for(drive(tmp_path, **kw), cfg)
    banner = html.split('class="word">', 1)[1].split("<", 1)[0]
    assert banner == word


def test_fail_banner_word(tmp_path, cfg):
    root = drive(tmp_path, [FakeRun("20261017.150000", images=False)])
    html = html_for(root, cfg)
    assert 'class="word">PROBLEM FOUND<' in html
    assert "What to do" in html


# --- the files it adds ------------------------------------------------------

def test_only_adds_files(tmp_path, cfg, capsys):
    root = drive(tmp_path)
    before = snapshot(root)
    assert main(["check", str(root), "--quiet"]) == 0
    first = snapshot(root)
    assert main(["check", str(root), "--quiet"]) == 0
    second = snapshot(root)
    for snap in (first, second):
        for k, v in before.items():
            assert snap[k] == v                        # nothing that was there changed
        new = set(snap) - set(before)
        assert new and all(Path(k).parts[0] == OUTPUT_DIR_NAME for k in new)
    for k in set(first) - set(before):
        assert second[k] == first[k]                   # first run's report untouched
    assert len(set(second) - set(first)) == 3          # html, json, csv


def test_same_second_gets_suffix_not_overwrite(tmp_path, cfg):
    root = drive(tmp_path)
    res = engine.run(root, cfg, days=[DAY])
    when = datetime(2026, 10, 28, 9, 0, 0)
    guard = WriteGuard(root)
    a = writer.write_reports(res, build(res, when), guard, when)
    b = writer.write_reports(res, build(res, when), guard, when)
    assert a.html != b.html and b.html.name.endswith("-2.html")
    assert a.html.read_bytes() and a.csv.exists() and b.csv.name.endswith("-2.csv")


def test_out_folder_used_and_drive_untouched(tmp_path, cfg):
    root = drive(tmp_path)
    before = snapshot(root)
    out = tmp_path / "elsewhere"
    out.mkdir()
    assert main(["check", str(root), "--quiet", "--out", str(out)]) == 0
    assert snapshot(root) == before
    assert len(list(out.iterdir())) == 3


def test_no_report_writes_nothing(tmp_path, cfg):
    root = drive(tmp_path)
    before = snapshot(root)
    assert main(["check", str(root), "--quiet", "--no-report"]) == 0
    assert snapshot(root) == before


def test_read_only_drive_says_so_and_writes_nothing(tmp_path, cfg, monkeypatch, capsys):
    root = drive(tmp_path)
    before = snapshot(root)

    def refuse(self, filename, data):
        raise OSError(30, "Read-only file system")
    monkeypatch.setattr(WriteGuard, "create_new", refuse)
    assert main(["check", str(root)]) == 0              # the check still ran
    err = capsys.readouterr().err
    assert "read-only" in err and "--out" in err
    assert snapshot(root) == before


def test_photo_csv_one_row_per_photo(tmp_path, cfg):
    root = drive(tmp_path, [FakeRun("20261017.150000", photos=12)])
    assert main(["check", str(root), "--quiet"]) == 0
    path = next((root / OUTPUT_DIR_NAME).glob("images_*.csv"))
    text = path.read_text(encoding="utf-8-sig")
    assert "No time here comes from a file date" in text
    rows = list(csv.reader(l for l in text.splitlines() if not l.startswith("#")))
    assert tuple(rows[0]) == COLUMNS
    body = rows[1:]
    assert len(body) == 24                              # 12 ROW + 12 Rear
    assert {r[COLUMNS.index("time_source")] for r in body} <= {"pulse", "startup_frame", "unverified", "none"}
    assert all(r[COLUMNS.index("gps_utc")] for r in body if r[COLUMNS.index("time_source")] == "pulse")


# --- the command and its exit codes ----------------------------------------

def test_exit_0_pass(tmp_path):
    assert main(["check", str(drive(tmp_path)), "--quiet", "--no-report"]) == 0


def test_exit_1_warn(tmp_path):
    assert main(["check", str(drive(tmp_path, qinertia=False)), "--quiet", "--no-report"]) == 1


def test_exit_2_fail(tmp_path):
    root = drive(tmp_path, [FakeRun("20261017.150000", images=False)])
    assert main(["check", str(root), "--quiet", "--no-report"]) == 2


@pytest.mark.parametrize("args", [
    ["check", "{missing}"],
    ["check", "{root}", "--days", "2026-10-17"],
    ["check", "{root}", "--days", "20250101"],
    ["check", "{root}", "--logs", "{missing}"],
    ["check", "{root}", "--config", "{missing}"],
    ["check"],
    ["frobnicate"],
])
def test_exit_3_bad_usage(tmp_path, args, capsys):
    root = drive(tmp_path)
    argv = [a.format(root=root, missing=tmp_path / "nope") for a in args]
    assert main(argv + ["--no-report"] if argv[:1] == ["check"] and len(argv) > 1 else argv) == 3


def test_exit_4_not_a_collection_drive(tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "notes.txt").write_text("hello")
    assert main(["check", str(empty), "--no-report"]) == 4
    assert "doesn't look like a collection drive" in capsys.readouterr().err


def test_json_on_stdout_matches_findings_file(tmp_path, capsys):
    root = drive(tmp_path, qinertia=False)
    assert main(["check", str(root), "--json"]) == 1
    out, err = capsys.readouterr()
    printed = json.loads(out)
    saved = json.loads(next((root / OUTPUT_DIR_NAME).glob("findings_*.json")).read_text(encoding="utf-8"))
    assert printed == saved
    assert printed["overall_verdict"] == "WARN" and err == ""


def test_days_all_and_list(tmp_path, capsys):
    root = build_drive(tmp_path / "F", [FakeDay(day="20261016", runs=[FakeRun("20261016.150000")], logs=True),
                                        FakeDay(day="20261017", runs=[FakeRun("20261017.150000")], logs=True)])
    main(["check", str(root), "--json", "--no-report"])
    assert [d["day"] for d in json.loads(capsys.readouterr().out)["days"]] == ["20261017"]
    main(["check", str(root), "--json", "--no-report", "--days", "all"])
    assert [d["day"] for d in json.loads(capsys.readouterr().out)["days"]] == ["20261016", "20261017"]


def test_version(capsys):
    assert main(["version"]) == 0
    assert capsys.readouterr().out.startswith("QCDATA ")


# --- the reference data -----------------------------------------------------

def test_reference_report(sample_root, tmp_path, capsys):
    out = tmp_path / "out"
    out.mkdir()
    code = main(["check", str(sample_root / "17thAnd16th"), "--days", "all", "--json", "--out", str(out)])
    data = json.loads(capsys.readouterr().out)
    days = {d["day"]: d for d in data["days"]}
    assert set(days) == {"20261016", "20261017"}
    assert days["20261017"]["verdict"] == "PASS"
    assert len(days["20261017"]["daily"]) == 28
    assert code == {"PASS": 0, "WARN": 1, "FAIL": 2}[data["overall_verdict"]]
    # crew comments are shown word for word
    html = next(out.glob("QCDATA_Report_*.html")).read_text(encoding="utf-8")
    assert "Delete File - due to ACS errors" in html
    assert "<h2" in html and html.count('id="day-') == 2
