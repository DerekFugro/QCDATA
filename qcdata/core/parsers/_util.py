"""Small helpers shared by the parsers."""

from __future__ import annotations

import logging

log = logging.getLogger("qcdata.parsers")


def to_float(text: str | None) -> float | None:
    if text is None:
        return None
    t = text.strip()
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def to_int(text: str | None) -> int | None:
    f = to_float(text)
    return int(f) if f is not None and f == int(f) else None


def strip_trailing_empty(cells: list[str]) -> list[str]:
    """CSV rows from the van end with a comma; drop the empty cells it leaves."""
    out = list(cells)
    while out and out[-1].strip() == "":
        out.pop()
    return out
