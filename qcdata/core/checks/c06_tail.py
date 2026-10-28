"""C6 - the photos reach the end of the run (photo count x step vs recorded end).

The same thing QC_Video checks. A run with a zero recorded end but photos is its
own WARN. 'Section Collected Short' runs are moved to "Explained by the crew" by
the engine.
"""

from __future__ import annotations

from qcdata.core.checks.base import Check, register, cap, rd_label
from qcdata.core.model import Severity


def tail_shortfall_m(rd, seq) -> tuple[float | None, float | None]:
    """(recorded end in m, shortfall in m) for one view; None if not computable."""
    ends = [r.end_distance_m for r in rd.export_rows if r.end_distance_m is not None]
    if not ends or seq is None or seq.count == 0:
        return None, None
    end = max(ends)
    return end, end - seq.names_mm[-1] / 1000.0


@register
class C06Tail(Check):
    id, title = "C6", "Photos reach the end of the run"

    def run(self, ctx):
        t = ctx.cfg.thresholds
        out = []
        for rd in ctx.checked_runs:
            for view, seq in rd.photos.items():
                end, short = tail_shortfall_m(rd, seq)
                if end is None:
                    continue
                if end == 0:
                    if seq.count > 1:
                        out.append(self.crew(ctx, Severity.WARN, rd.run, view,
                            f"{cap(rd_label(rd))} ({view}) has {seq.count} photos but was "
                            f"exported with zero length.",
                            f"{rd.run}/{view}: EndDistanceStamp 0 with {seq.count} photos "
                            f"(last {seq.names_mm[-1] / 1000:.2f} m).",
                            "Check this session in the Daily; tell the office if it should have been kept."))
                    continue
                if short > t.c6_warn_m:
                    sev = Severity.FAIL if short > t.c6_fail_m else Severity.WARN
                    out.append(self.crew(ctx, sev, rd.run, view,
                        f"{cap(rd_label(rd))} ({view}): the photos stop {short:.1f} m before "
                        f"the end of the session.",
                        f"{rd.run}/{view}: last photo {seq.names_mm[-1] / 1000:.2f} m, recorded end "
                        f"{end:.2f} m, shortfall {short:.2f} m.",
                        "The end of this session has no photos. Re-collect it if needed, and tell the office.",
                        shortfall_m=round(short, 2), end_m=round(end, 2)))
        return out
