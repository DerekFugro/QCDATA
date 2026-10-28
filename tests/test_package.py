"""Phase 1 sanity tests: the package imports, reports its version, and the
engine stays free of Qt."""

from __future__ import annotations

import re
from pathlib import Path

import qcdata
from qcdata.cli.main import main

PACKAGE_DIR = Path(qcdata.__file__).parent
QT_IMPORT = re.compile(r"^\s*(from|import)\s+(PySide6|shiboken6)\b", re.MULTILINE)


def test_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", qcdata.__version__)


def test_cli_version_prints_and_exits_zero(capsys) -> None:
    assert main(["version"]) == 0
    assert qcdata.__version__ in capsys.readouterr().out


def test_cli_check_not_built_yet_exits_3() -> None:
    assert main(["check", "F:\\"]) == 3


def test_core_never_imports_qt() -> None:
    offenders = [
        str(p.relative_to(PACKAGE_DIR))
        for p in (PACKAGE_DIR / "core").rglob("*.py")
        if QT_IMPORT.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"Qt imported in core: {offenders}"
