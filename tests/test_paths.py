"""The write guard: QCDATA only ever ADDS files on the data drive."""

from __future__ import annotations

import pytest

from qcdata.core.paths import WriteGuard, WriteRefused


def test_creates_new_file_in_qcdata_folder(tmp_path):
    g = WriteGuard(tmp_path)
    p = g.create_new("report.html", b"hello")
    assert p == (tmp_path / "_QCDATA" / "report.html").resolve() and p.read_bytes() == b"hello"


def test_never_overwrites_name_clash_gets_suffix(tmp_path):
    g = WriteGuard(tmp_path)
    first = g.create_new("r.html", b"one")
    second = g.create_new("r.html", b"two")
    assert first.read_bytes() == b"one" and second.name == "r-2.html"


@pytest.mark.parametrize("name", ["../escape.txt", "..", "sub/x.txt", "C:\\x.txt", "", ".hidden", "a:b"])
def test_traversal_and_odd_names_refused(tmp_path, name):
    with pytest.raises(WriteRefused):
        WriteGuard(tmp_path).create_new(name, b"x")


def test_app_files_only(tmp_path):
    data = tmp_path / "drive"
    data.mkdir()
    app = tmp_path / "app"
    app.mkdir()
    cfg_file = app / "config.yaml"
    cfg_file.write_text("old")
    g = WriteGuard(data, app_files=[cfg_file])
    g.rewrite_app_file(cfg_file, b"new")
    assert cfg_file.read_text() == "new"
    with pytest.raises(WriteRefused):
        g.rewrite_app_file(app / "other.yaml", b"x")
    on_drive = data / "config.yaml"
    on_drive.write_text("data")
    with pytest.raises(WriteRefused):
        WriteGuard(data, app_files=[on_drive]).rewrite_app_file(on_drive, b"x")


def test_output_folder_must_be_a_real_folder(tmp_path):
    (tmp_path / "_QCDATA").write_text("i am a file")
    with pytest.raises(WriteRefused):
        WriteGuard(tmp_path).create_new("r.html", b"x")
