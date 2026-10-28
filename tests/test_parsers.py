"""Every parser against small hand-written files: normal rows, the van's quirks,
and malformed lines (which must be skipped, never raised)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from qcdata.core.model import LaserFile, RunId
from qcdata.core.parsers.daily import comment_kind, parse_daily
from qcdata.core.parsers.export_log import collect_runs, parse_run_list
from qcdata.core.parsers.gocator import parse_laser
from qcdata.core.parsers.images import scan_view
from qcdata.core.parsers.qc_video import parse_qc_video
from qcdata.core.parsers.sbg import WRAP, UtcConverter, align, parse_event_file, parse_utc_file, unwrap
from qcdata.core.parsers.settings import parse_settings
from qcdata.core.parsers.status import parse_status_messages


def w(p: Path, text: str, nl: str = "\n") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.replace("\n", nl).encode("utf-8"))
    return p


# ------------------------------------------------------------ export log
EXPORT = """ARAN01_Export_20261017171030
Start Date: 10/17/2026 12:00:00 AM
End Date: 10/17/2026 11:00:00 PM

UniqueRun,SectionName,BeginDistanceStamp,EndDistanceStamp,BeginChainage,EndChainage,
[20261017.142417],303720,5.36,50.2,0,0.044,
garbage line,,
[20261017.142650],303740,0,0,0,0,
"""


def test_export_log_rows_dates_and_skips(tmp_path):
    el = parse_run_list(w(tmp_path / "a_log.csv", EXPORT))
    assert el.title == "ARAN01_Export_20261017171030"
    assert el.start_date.startswith("10/17/2026") and el.end_date.startswith("10/17/2026")
    assert [str(r.run) for r in el.rows] == ["20261017.142417", "20261017.142650"]
    assert el.rows[0].end_distance_m == 50.2
    assert len(el.skipped) == 1


def test_export_log_without_trailing_comma(tmp_path):
    el = parse_run_list(w(tmp_path / "b_log.csv", EXPORT.replace(",\n", "\n")))
    assert len(el.rows) == 2


def test_collect_runs_dedupes_copies_and_unions_exports(tmp_path):
    a = parse_run_list(w(tmp_path / "a_log.csv", EXPORT))
    b = parse_run_list(w(tmp_path / "copy_log.csv", EXPORT))
    c = parse_run_list(w(tmp_path / "c_log.csv", EXPORT.replace("142650", "160000")))
    runs = collect_runs([a, b, c])["20261017"]
    assert sorted(map(str, runs)) == ["20261017.142417", "20261017.142650", "20261017.160000"]
    assert all(len(v) == 1 for v in runs.values())


def test_process_log_is_not_a_run_list(tmp_path):
    p = w(tmp_path / "x_export_log.csv", "ARAN01_Export_1\nIDExportLogDetail,ExportDBName\n19,a\n")
    el = parse_run_list(p)
    assert el.rows == [] and el.skipped


# ------------------------------------------------------------ daily
DAILY = """FILENAME,ARAN,HEADER,Comments,Initials,Status,GPS Mode,LatBeg,LongBeg,Length,CollLength,Date,,
,,,,,,,,,,,,,
[0],1700,314720,Other - sidewalk does not exist,,U,,,,0.017,0.017,Fri,,
[20261017.142417],1700,303720,,SJO,C,NoSolution,33.9,-80.8,0.022,0.027,Sat,,
[20261017.142650],1700,303740,Delete File - Due to NAN ACS error,SJO,X,NoSolution,,,0.008,0,Sat,,
[20261017.160000],1700,303750,Other - narrow sidewalk - Section Collected Short - Due to Dead End Start,SJO,v,,,,,,Sat,,
,,,,,,,,,,,,,Averages:,,
,,,,,,,,,,,,,,
ACS Version 2.6.5.774,,
Daily Report Version 1.0.0.0,,
Time in motion - 2h 0m 24s,,
something odd,,
"""


def test_daily_runs_status_meta_and_columns_by_name(tmp_path):
    d = parse_daily(w(tmp_path / "Daily_ARAN01_20261017.csv", DAILY), "20261017")
    assert len(d.rows) == 4 and len(d.run_rows) == 3
    zero = d.rows[0]
    assert zero.run is None and zero.raw_filename == "[0]"
    r1, r2, r3 = d.run_rows
    assert (r1.status, r1.is_checked, r1.lat_beg, r1.gps_mode) == ("C", True, 33.9, "NoSolution")
    assert (r2.status, r2.is_checked, r2.comment_kind) == ("X", False, "delete")
    assert (r3.status, r3.is_checked, r3.comment_kind) == ("V", True, "collected_short")
    assert r3.lat_beg is None   # blank positions are valid
    assert d.meta["acs_version"] == "2.6.5.774"
    assert d.meta["time_in_motion"] == "2h 0m 24s"
    assert d.meta["has_averages_row"] == "yes"
    assert [s.reason for s in d.skipped] == ["unrecognised row: 'something odd'"]


def test_comment_kinds():
    assert comment_kind("") == ""
    assert comment_kind("Delete File - due to ACS errors") == "delete"
    assert comment_kind("Section Collected Short - Due to lack of start") == "collected_short"
    assert comment_kind("Other - x - Section Collected Short - y") == "collected_short"
    assert comment_kind("Other - Sidewalk deviation") == "other"


# ------------------------------------------------------------ status messages
STATUS = """FileName,Severity,Message,Module,StatusDate,DistanceStamp,
[20261017.165541],Warning,9057 - Camera ROW capture interval speed limit exceeded. Please slow down image frames may get lost,Video,10/17/2026 4:55:56 PM,9.57,
[20261016.090537],Information,End of Section in 285 Meters,Mission Management,10/16/2026 9:05:45 AM,,
[20261017.170000],Information,A message, with, commas,Data Manager,10/17/2026 5:00:00 PM,1.5,
bad
"""


def test_status_messages_codes_commas_blank_distance(tmp_path):
    msgs, skipped = parse_status_messages(w(tmp_path / "s.csv", STATUS))
    assert len(msgs) == 3 and len(skipped) == 1
    assert msgs[0].code == 9057 and msgs[0].module == "Video" and msgs[0].distance == 9.57
    assert msgs[0].time == datetime(2026, 10, 17, 16, 55, 56)
    assert msgs[1].distance is None and msgs[1].module == "Mission Management"
    assert msgs[2].message == "A message, with, commas" and msgs[2].module == "Data Manager"


# ------------------------------------------------------------ photos
def test_photo_names_step_holes_and_other_files(tmp_path):
    folder = tmp_path / "ROW"
    folder.mkdir()
    for k in (1, 2, 3, 5, 6):
        (folder / f"{k * 750:012d}.JPG").write_bytes(b"")
    (folder / "Thumbs.db").write_bytes(b"")
    seq = scan_view(RunId("20261017.150000"), "ROW", folder)
    assert seq.count == 5 and seq.step_mm == 750
    assert seq.missing_mm == (3000,)
    assert seq.other_files == ("Thumbs.db",)
    assert seq.photo_number(75000) == 100


def test_single_photo_has_no_step(tmp_path):
    folder = tmp_path / "Rear"
    folder.mkdir()
    (folder / "000000000750.jpg").write_bytes(b"")
    seq = scan_view(RunId("20261017.150000"), "Rear", folder)
    assert seq.step_mm is None and seq.missing_mm == () and seq.photo_number(750) == 1


# ------------------------------------------------------------ lasers
HDR = "frameIndex,timestamp,ptpTimestamp,encoder,numberOfProfilePoints,x0,z0\n"


def test_laser_missing_empty_present_and_gaps(tmp_path):
    run = RunId("20261017.150000")
    assert parse_laser(run, "L", tmp_path / "nope.csv").state == "missing"
    assert parse_laser(run, "L", w(tmp_path / "e.csv", HDR)).state == "empty"
    rows = "".join(f"{i},{i},{1_000_000 + i * 10_000},{i * 136},424,1,2\n" for i in (1, 2, 3, 6, 7))
    lf: LaserFile = parse_laser(run, "R", w(tmp_path / "p.csv", HDR + rows + "junk\n"))
    assert lf.state == "present" and lf.rows == 5 and lf.skipped_lines == 1
    assert lf.frame_gaps == ((3, 6),) and lf.missing_frames == 2
    assert lf.first_ptp_us == 1_010_000 and lf.last_ptp_us == 1_070_000 and lf.lock_rows_skipped == 0


def test_laser_ptp_lock_jump_at_start_only(tmp_path):
    run = RunId("20261017.150000")
    ptps = [5, 7, 9_000_000_000_000, 9_000_000_010_000, 9_000_000_020_000]
    body = "".join(f"{i + 1},0,{p},0,424,1,2\n" for i, p in enumerate(ptps))
    lf = parse_laser(run, "L", w(tmp_path / "j.csv", HDR + body))
    assert lf.lock_rows_skipped == 2 and lf.first_ptp_us == 9_000_000_000_000
    # a long stop (20 s) is NOT a lock jump
    body = "".join(f"{i + 1},0,{p},0,424,1,2\n" for i, p in enumerate([0, 10_000, 20_010_000, 20_020_000]))
    assert parse_laser(run, "L", w(tmp_path / "s.csv", HDR + body)).lock_rows_skipped == 0


# ------------------------------------------------------------ SBG
def test_trigger_parser_handles_leading_spaces(tmp_path):
    """Regression test: right-aligned timestamps with leading spaces, digit count
    changing mid-file, CRLF. A starts-with-a-digit parser silently drops rows."""
    text = ("timestamp\tstatus\ttimeOffset0\n(us)\t(na)\t(us)\n"
            "  88753988\t0x0000\t0\n 879861643\t0x0000\t0\n1050947943\t0x0000\t0\n")
    values, rollovers, skipped = parse_event_file(w(tmp_path / "eventOutA.txt", text, "\r\n"))
    assert values == [88753988, 879861643, 1050947943] and rollovers == 0 and skipped == 0


def test_counter_rollover_unwrap():
    vals, n = unwrap([4_294_000_000, 4_294_900_000, 1_000_000, 2_000_000])
    assert n == 1 and vals == [4_294_000_000, 4_294_900_000, WRAP + 1_000_000, WRAP + 2_000_000]


def test_utc_table_and_align_after_independent_unwrap(tmp_path):
    ut = ("timestamp\tstatus\tgpsTimeOfWeek\tyear\tmonth\tday\thour\tminute\tsecond\tnanosecond\n"
          "(us)\t(na)\t(ms)\t(yyyy)\t(mm)\t(dd)\t(hh)\t(mm)\t(s)\t(ns)\n"
          "4294000000\t0x00a7\t0\t2026\t10\t17\t21\t3\t7\t0\n"
          "   32704\t0x00a7\t0\t2026\t10\t17\t21\t3\t8\t0\n"
          "1000032704\t0x00a7\t0\t2026\t10\t17\t21\t3\t9\t0\n"
          "0\t0x0000\t0\t1970\t1\t1\t0\t0\t0\t0\n")
    table, skipped = parse_utc_file(w(tmp_path / "utcTime.txt", ut))
    assert len(table) == 3 and skipped == 1
    assert table[1][0] == WRAP + 32704
    # pulses that start after the wrap, unwrapped on their own, must be shifted onto the table
    pulses = align([500_000_000], table)
    assert pulses == [WRAP + 500_000_000]
    conv = UtcConverter(table)
    assert abs(conv.to_utc(WRAP + 32704) - table[1][1]) < 1e-6


# ------------------------------------------------------------ QC_Video / settings
def test_qc_video_rows_note_and_trailing_comma(tmp_path):
    text = ("Session Name,Error,View,First File,Last File,Begin Chainage,End Chainage,Image Count,\n"
            "[20261020.121954],Image missing,ROW,000000005250.JPG,000000010324.JPG,0.00525,0.010324027,8,"
            "File Deleted - Did not affect collection\n"
            "[20261009.102755],Image missing,ROW,000000063750.JPG,000000075369.JPG,0.06375,0.0753,17\n")
    rows, skipped = parse_qc_video(w(tmp_path / "QC_Video.csv", text))
    assert len(rows) == 2 and not skipped
    assert rows[0].note == "File Deleted - Did not affect collection" and rows[0].image_count == 8
    assert rows[1].note == "" and rows[1].end_km == 0.0753
    assert parse_qc_video(w(tmp_path / "e.csv", text.splitlines()[0] + "\n"))[0] == []


def test_settings_bom_and_hostile_xml(tmp_path):
    ok = ("﻿<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<ARANSettings><misc><ACS_Version>"
          "<Version>2.6.5.774</Version></ACS_Version><ARAN_Name><Name>ARAN01</Name></ARAN_Name>"
          "</misc></ARANSettings>")
    s = parse_settings(w(tmp_path / "ARAN01_Settings_20261017.xml", ok))
    assert s.parsed and s.acs_version == "2.6.5.774" and s.van_name == "ARAN01"
    bomb = ('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
            "<ARANSettings>&b;</ARANSettings>")
    s = parse_settings(w(tmp_path / "bomb.xml", bomb))
    assert not s.parsed and s.error
