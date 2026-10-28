"""C15 - dropped photos: photos vs camera pulses (+1 start-up frame), per view.

Pulses less than min_pulse_gap_s after the previous one get no photo and are
already removed. 1-2 short at the end is normal (cameras stop while moving);
short at the start means the cameras weren't ready; MORE photos than
pulses + 1 is a real problem.
"""

from __future__ import annotations

import bisect

from qcdata.core.checks._pulses import photo_vs_pulses
from qcdata.core.checks.base import Check, register, cap, run_label
from qcdata.core.model import Severity

RESPONSE_WINDOW_US = 2000


@register
class C15Pulses(Check):
    id, title = "C15", "No dropped photos"

    def run(self, ctx):
        t = ctx.cfg.thresholds
        d, out = ctx.day, []
        for rd in ctx.checked_runs:
            label = cap(run_label(rd.run))
            if rd.sbg is None or rd.pulse_plan is None:
                continue                                  # C11 reports the missing DataLogger
            for view, seq in rd.photos.items():
                if seq is None:
                    continue
                r = photo_vs_pulses(rd, seq, d)
                if r is None:
                    continue
                tech = (f"{rd.run}/{view}: photos={r.photos}, pulses={r.raw_pulses} "
                        f"(no-photo {r.no_photo_pulses}), expected photos={r.expected}, "
                        f"pulses before camera start={r.pulses_before_camera_start}, "
                        f"after camera stop={r.pulses_after_camera_stop}.")
                if r.diff > 0:
                    out.append(self.crew(ctx, Severity.FAIL, rd.run, view,
                        f"{label} ({view}) has {r.diff} more photo(s) than camera pulses — that shouldn't happen.",
                        tech, "Tell the office."))
                elif r.short:
                    if r.pulses_before_camera_start:
                        out.append(self.crew(ctx, Severity.WARN, rd.run, view,
                            f"{label} ({view}): the cameras weren't ready at the start — {r.short} photo(s) "
                            f"missing at the start.", tech,
                            "The start of this run has no photos. Re-collect it if needed, and tell the office."))
                    elif r.short <= t.normal_end_short:
                        where = "at the end" if r.pulses_after_camera_stop else "(position unknown)"
                        out.append(self.note(ctx, rd.run, view,
                            f"{label} ({view}): {r.short} photo(s) short {where} — normal, the cameras "
                            f"stop while still moving.", tech))
                    else:
                        where = "at the end" if r.pulses_after_camera_stop else "(position unknown — no camera log)"
                        out.append(self.crew(ctx, Severity.WARN, rd.run, view,
                            f"{label} ({view}): {r.short} photo(s) missing {where}.", tech,
                            "Copy this run's photos again; if still short, photos were lost — tell the office."))
            if rd.pulse_plan.no_photo_pulses:
                n = len(rd.pulse_plan.no_photo_pulses)
                out.append(self.note(ctx, rd.run, "",
                    f"{label}: {n} pulse(s) came less than {t.min_pulse_gap_s} s after the previous one, so "
                    f"they have no photo (normal).",
                    f"{rd.run}: no-photo pulse indices {list(rd.pulse_plan.no_photo_pulses)}."))
            # Cross-checks on the other pulse files (roles unconfirmed) - technical only.
            a = rd.sbg.pulses_us
            if rd.sbg.pulses_b_us is not None and rd.sbg.pulses_b_us != a:
                out.append(self.note(ctx, rd.run, "",
                    f"{label}: eventOutB doesn't match eventOutA ({len(rd.sbg.pulses_b_us)} vs {len(a)} pulses).",
                    f"{rd.run}: eventOutB differs from eventOutA."))
            if rd.sbg.responses_us is not None:
                resp = rd.sbg.responses_us
                missing = sum(1 for p in a if not ((j := bisect.bisect_left(resp, p)) < len(resp)
                                                    and resp[j] - p < RESPONSE_WINDOW_US))
                if missing:
                    out.append(self.note(ctx, rd.run, "",
                        f"{label}: {missing} pulse(s) have no matching eventInA response.",
                        f"{rd.run}: {missing} eventOutA pulses without eventInA within 2 ms."))
        return out
