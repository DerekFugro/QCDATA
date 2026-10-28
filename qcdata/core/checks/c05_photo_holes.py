"""C5 - no photos missing from the middle of a run (a gap in the photo numbers)."""

from __future__ import annotations

from qcdata.core.checks.base import Check, register, cap, run_label
from qcdata.core.model import Severity


@register
class C05PhotoHoles(Check):
    id, title = "C5", "No photos missing mid-run"

    def run(self, ctx):
        out = []
        expected = ctx.cfg.expected_step_mm
        for rd in ctx.checked_runs:
            for view, seq in rd.photos.items():
                if seq is None:
                    continue
                if seq.step_mm and seq.step_mm != expected:
                    out.append(self.crew(ctx, Severity.WARN, rd.run, view,
                        f"{cap(run_label(rd.run))} ({view}): photos are spaced {seq.step_mm} mm "
                        f"apart, not the usual {expected} mm.",
                        f"{rd.run}/{view}: derived step {seq.step_mm} mm vs expected {expected} mm.",
                        "Tell the office — the camera spacing setting may have changed."))
                if seq.missing_mm:
                    first = ", ".join(f"{m:012d}.jpg" for m in seq.missing_mm[:5])
                    more = f" and {len(seq.missing_mm) - 5} more" if len(seq.missing_mm) > 5 else ""
                    out.append(self.crew(ctx, Severity.FAIL, rd.run, view,
                        f"{cap(run_label(rd.run))} ({view}): {len(seq.missing_mm)} photo(s) are "
                        f"missing from the middle of the run.",
                        f"{rd.run}/{view}: missing {first}{more}.",
                        "Copy this run's photos again. If they are still missing, they were lost — tell the office.",
                        missing=[f"{m:012d}.jpg" for m in seq.missing_mm]))
        return out
