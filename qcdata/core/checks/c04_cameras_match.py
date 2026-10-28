"""C4 - ROW and Rear have the same number of photos."""

from __future__ import annotations

from qcdata.core.checks.base import Check, register, cap, run_label
from qcdata.core.model import Severity


@register
class C04CamerasMatch(Check):
    id, title = "C4", "Both cameras have the same photo count"

    def run(self, ctx):
        out = []
        for rd in ctx.checked_runs:
            row, rear = rd.photos.get("ROW"), rd.photos.get("Rear")
            if row is None or rear is None or row.count == rear.count:
                continue
            out.append(self.crew(ctx, Severity.FAIL, rd.run, "",
                f"{cap(run_label(rd.run))}: the two cameras have different numbers of photos "
                f"(ROW {row.count}, Rear {rear.count}).",
                f"{rd.run}: ROW={row.count} Rear={rear.count}.",
                "Copy this run's photos again. If the counts still differ, photos were lost — tell the office."))
        return out
