"""C16 - stops: long gaps between camera pulses (information only; stopping is normal)."""

from __future__ import annotations

from qcdata.core.checks._pulses import pulse_utcs
from qcdata.core.checks.base import Check, register, cap, rd_label


@register
class C16Stops(Check):
    id, title = "C16", "Stops during runs"

    def run(self, ctx):
        stop_s = ctx.cfg.thresholds.stop_s
        out = []
        for rd in ctx.checked_runs:
            utcs = pulse_utcs(rd)
            stops = [(i + 3, round(b - a, 1)) for i, (a, b) in enumerate(zip(utcs, utcs[1:])) if b - a >= stop_s]
            if stops:
                desc = ", ".join(f"{s} s before photo {n}" for n, s in stops)
                out.append(self.note(ctx, rd.run, "",
                    f"{cap(rd_label(rd))} stopped {len(stops)} time(s): {desc}.",
                    f"{rd.run}: pulse gaps >= {stop_s} s: {stops}", stops=stops))
        return out
