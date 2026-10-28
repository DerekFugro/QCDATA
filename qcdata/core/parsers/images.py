"""Photo folders - Images/<run>/<view>/. File NAMES only; photos are never opened.

Names are photo count x step (750 mm in all sample data), zero-padded to 12
digits: 000000075000.jpg is photo 100. The step is derived per run, never
assumed.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path

from qcdata.core.model import PhotoSequence, RunId

_PHOTO = re.compile(r"^(\d{1,12})\.jpe?g$", re.IGNORECASE)
VIEWS = ("ROW", "Rear")


def find_view_dir(run_dir: Path, view: str) -> Path | None:
    try:
        with os.scandir(run_dir) as it:
            for e in it:
                if e.is_dir() and e.name.lower() == view.lower():
                    return Path(e.path)
    except OSError:
        return None
    return None


def scan_view(run: RunId, view: str, folder: Path) -> PhotoSequence:
    names: list[int] = []
    other: list[str] = []
    try:
        with os.scandir(folder) as it:
            for e in it:
                m = _PHOTO.match(e.name)
                if m and e.is_file():
                    names.append(int(m.group(1)))
                else:
                    other.append(e.name)
    except OSError:
        pass
    names.sort()
    step = None
    missing: tuple[int, ...] = ()
    if len(names) >= 2:
        step = Counter(b - a for a, b in zip(names, names[1:])).most_common(1)[0][0]
        if step > 0:
            present = set(names)
            missing = tuple(x for x in range(names[0], names[-1] + 1, step) if x not in present)
    return PhotoSequence(run=run, view=view, folder=folder, names_mm=tuple(names),
                         step_mm=step, missing_mm=missing, other_files=tuple(sorted(other)))
