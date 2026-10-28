"""RunId and config.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest

from qcdata.config.schema import ConfigError, default_config, load_config
from qcdata.core.model import RunId


@pytest.mark.parametrize("text", ["[20261017.153218]", "20261017.153218", " [20261017.153218] "])
def test_runid_round_trips_bracketed_and_bare(text):
    r = RunId.parse(text)
    assert r is not None and r.value == "20261017.153218"
    assert r.bracketed == "[20261017.153218]"
    assert RunId.parse(r.bracketed) == RunId.parse(str(r)) == r


@pytest.mark.parametrize("text", ["[0]", "20261017", "20261017.256000", "ACS Version 2.6", "", None,
                                  "ReviewData_20261009.134020.csv"])
def test_runid_rejects_non_runs(text):
    assert RunId.parse(text) is None


def test_runid_day_and_tolerance():
    a, b = RunId("20261017.154208"), RunId("20261017.154209")
    assert a.day == "20261017"
    assert a.within(b, 2) and not a.within(RunId("20261017.154212"), 2)
    assert not a.within(RunId("20261018.154208"), 2)


def test_project_config_matches_defaults():
    root = Path(__file__).resolve().parents[1]
    assert load_config(root / "config.yaml") == default_config()


def test_missing_config_gives_defaults(tmp_path):
    assert load_config(tmp_path / "nope.yaml") == default_config()


@pytest.mark.parametrize("text,needle", [
    ("thresholds:\n  stop_seconds: 5\n", "thresholds.stop_seconds"),
    ("checks:\n  C1: yes please\n", "checks.C1"),
    ("thresholds:\n  stop_s: fast\n", "thresholds.stop_s"),
    ("thresholds:\n  c6_warn_m: 9\n  c6_fail_m: 3\n", "c6_fail_m"),
    ("local_timezone: Mars/Olympus\n", "local_timezone"),
    ("data_drives: [F]\n", "data_drives"),
    ("- just\n- a list\n", "key: value"),
])
def test_bad_config_names_the_key(tmp_path, text, needle):
    p = tmp_path / "config.yaml"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError) as e:
        load_config(p)
    assert needle in str(e.value)


def test_int_accepted_where_float_expected(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("thresholds:\n  stop_s: 7\n", encoding="utf-8")
    assert load_config(p).thresholds.stop_s == 7.0
