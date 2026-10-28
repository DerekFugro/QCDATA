"""C9 - GPS mode in the Daily (technical only; blank positions are valid)."""

from __future__ import annotations

from qcdata.core.checks.base import Check, register


@register
class C09GpsMode(Check):
    id, title = "C9", "Daily GPS mode"

    def run(self, ctx):
        rows = [rd.daily for rd in ctx.checked_runs if rd.daily]
        if rows and all(r.gps_mode.lower() == "nosolution" for r in rows):
            return [self.note(ctx, None, "",
                f"Every checked run in the Daily shows GPS mode “NoSolution” — positions may not "
                f"be post-processed yet.", f"{len(rows)} rows with GPS Mode=NoSolution.")]
        return []
