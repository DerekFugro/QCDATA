"""C17 - time sync (technical section only): PC clock vs GPS, drift, photo-time self-check."""

from __future__ import annotations

from qcdata.core.checks.base import Check, register


def _hms(seconds: float) -> str:
    s = abs(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{int(h)} h {int(m)} min {sec:.1f} s"


@register
class C17TimeSync(Check):
    id, title = "C17", "Time sync"

    def run(self, ctx):
        d, t, out = ctx.day, ctx.cfg.thresholds, []
        if d.offsets:
            deltas = [o.delta_s for o in d.offsets]
            first, last = deltas[0], deltas[-1]
            drift = max(deltas) - min(deltas)
            tz_s = d.offsets[0].display_minus_utc_s - d.offsets[0].delta_s   # display = PC unix + tz
            tz = f"UTC{'+' if tz_s >= 0 else '−'}{abs(tz_s) / 3600:g}"
            ahead = "ahead of" if first >= 0 else "behind"
            note = " Note: it drifted more than usual." if drift > t.clock_drift_note_s else ""
            out.append(self.note(ctx, None, "",
                f"The van PC's clock was {_hms(first)} {ahead} GPS time (PC set to {tz}); it drifted "
                f"{drift:.2f} s during the day.{note}",
                f"SBG.log CallbackUtc: delta {first:.3f} -> {last:.3f} s ({len(deltas)} samples); "
                f"display-UTC {d.offsets[0].display_minus_utc_s:.3f} s.",
                delta_first=round(first, 3), delta_last=round(last, 3), drift=round(drift, 3)))
        elif d.clock:
            out.append(self.note(ctx, None, "", "PC clock taken from the camera log (no SBG log for this day)."))
        timing = ctx.timing
        if timing.log_delay_s is not None:
            bad = sorted(f"{run}/{view}" for run, views in timing.runs.items()
                         for view, rt in views.items() if not rt.verified)
            msg = (f"Photo-time self-check: {timing.residual_count} camera-log lines, typical logging delay "
                   f"{timing.log_delay_s:.2f} s; ")
            msg += f"{len(bad)} run-camera pair(s) did NOT match: {', '.join(bad)}." if bad else "all matched."
            if abs(timing.log_delay_s) > 1.0:
                msg += " The camera log and the SBG log disagree by more than 1 s."
            out.append(self.note(ctx, None, "", msg, msg, unverified=bad))
        return out
