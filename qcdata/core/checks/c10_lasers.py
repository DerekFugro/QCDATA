"""C10 - laser files, each side on its own: missing, empty, short, frame gaps, L/R counts."""

from __future__ import annotations

from qcdata.core.checks._pulses import laser_vs_pulses
from qcdata.core.checks.base import SIDE_NAMES, Check, register, cap, rd_label
from qcdata.core.model import Severity


@register
class C10Lasers(Check):
    id, title = "C10", "Laser files complete"

    def run(self, ctx):
        t = ctx.cfg.thresholds
        out = []
        for rd in ctx.checked_runs:
            if not rd.has_gocator_dir:
                continue                      # C3 already reports the missing folder
            if not rd.lasers:
                continue                      # laser files weren't read in this session (quick mode)
            label = cap(rd_label(rd))
            for side in ("L", "R"):
                lf = rd.lasers.get(side)
                name = SIDE_NAMES[side]
                if lf is None or lf.state == "missing":
                    out.append(self.crew(ctx, Severity.FAIL, rd.run, name,
                        f"{label}: the {name} file is missing.",
                        f"{rd.run}: no {rd.run.value.replace('.', 'T')}{side}.csv.",
                        "Copy this session's laser files again. If the file isn't on the van, tell the office."))
                    continue
                if lf.state == "empty":
                    out.append(self.crew(ctx, Severity.WARN, rd.run, name,
                        f"{label}: the {name} file is empty (no laser data in it).",
                        f"{lf.path.name}: header only, 0 rows.",
                        "Copy the file again. If it is empty on the van too, tell the office."))
                    continue
                if lf.missing_frames:
                    out.append(self.crew(ctx, Severity.WARN, rd.run, name,
                        f"{label}: {lf.missing_frames} laser profile(s) are missing from the {name} data.",
                        f"{lf.path.name}: frameIndex gaps {list(lf.frame_gaps)[:5]}.",
                        "Tell the office — some laser profiles were dropped.",
                        gaps=[list(g) for g in lf.frame_gaps]))
                lp = laser_vs_pulses(rd, lf, ctx.cfg)
                total = len(rd.pulse_plan.photo_pulses_us) if rd.pulse_plan else 0
                if lp is not None and total and max(lp.pulses_before_first_row, lp.pulses_after_last_row) >= total:
                    ptp = [m.message for m in ctx.day.status
                           if m.run == rd.run and m.code == 2501 and f"GoCator {side}" in m.message]
                    why = f" The status log says \u201c{ptp[0]}\u201d." if ptp else ""
                    out.append(self.crew(ctx, Severity.WARN, rd.run, name,
                        f"{label}: the {name} recorded no data during the session ({lf.rows} row(s), all outside "
                        f"the session).{why}",
                        f"{lf.path.name}: {lf.rows} rows, none between the first and last camera pulse "
                        f"({total} pulses).{why}",
                        "This session has photos but no laser data. Tell the office."))
                    continue
                if lp is not None:
                    for count, where, word in ((lp.pulses_before_first_row, "start", "starts"),
                                               (lp.pulses_after_last_row, "end", "stops")):
                        if count == 0:
                            continue
                        when = "after" if where == "start" else "before"
                        plain = (f"{label}: the {name} {word} {count} camera pulse(s) "
                                 f"(≈{count * 0.75:g} m) {when} the cameras.")
                        tech = f"{lf.path.name}: {count} pulse(s) outside the laser data at the {where}."
                        if count > t.laser_short_pulses:
                            out.append(self.crew(ctx, Severity.WARN, rd.run, name, plain, tech,
                                "That stretch has photos but no laser data. Tell the office."))
                        else:
                            out.append(self.note(ctx, rd.run, name, plain + " Within the normal allowance.", tech))
            l, r = rd.lasers.get("L"), rd.lasers.get("R")
            if l and r and l.state == r.state == "present":
                diff = abs(l.rows - r.rows)
                allowed = max(t.c10_max_abs_diff, t.c10_max_pct_diff / 100 * max(l.rows, r.rows))
                if diff > allowed:
                    out.append(self.crew(ctx, Severity.WARN, rd.run, "lasers",
                        f"{label}: the left and right laser files have very different lengths "
                        f"({l.rows} and {r.rows} rows).",
                        f"{rd.run}: L={l.rows} R={r.rows}, diff {diff} > allowed {allowed:.0f}.",
                        "Tell the office — one laser may have stopped early."))
        return out
