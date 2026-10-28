"""ARAN01_Settings_<day>.xml - parsed safely (defusedxml); only identifying fields
are read. Settings comparison is ProjectCompare's job, not QCDATA's."""

from __future__ import annotations

from pathlib import Path

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from qcdata.core.model import SettingsInfo


def parse_settings(path: Path) -> SettingsInfo:
    path = Path(path)
    try:
        root = SafeET.parse(str(path)).getroot()
    except (DefusedXmlException, SafeET.ParseError, OSError) as exc:
        return SettingsInfo(path, None, None, False, f"{type(exc).__name__}: {exc}")
    def text(xpath: str) -> str | None:
        el = root.find(xpath)
        return el.text.strip() if el is not None and el.text else None
    return SettingsInfo(path, text("misc/ACS_Version/Version"), text("misc/ARAN_Name/Name"), True, None)
