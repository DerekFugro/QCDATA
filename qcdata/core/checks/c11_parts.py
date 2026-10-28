"""C11 - every part of the day present, checked separately.

Copies often miss whole pieces (one copy arrived with no SBGData DataLogger
folders for a day and without the previous day's Qinertia projects).
"""

from __future__ import annotations

from qcdata.core.checks.base import Check, register, cap, run_label
from qcdata.core.model import Severity


@register
class C11Parts(Check):
    id, title = "C11", "Every part of the day present"

    def run(self, ctx):
        d, out = ctx.day, []
        yymmdd = d.day[2:]
        has_photos = any(rd.has_image_dir for rd in ctx.checked_runs)
        if not d.sbg_day_dir_present:
            out.append(self.crew(ctx, Severity.WARN, None, "",
                f"The SBG data folder for {d.day} is missing (SBGData\\{yymmdd}).",
                f"No SBGData/{yymmdd} folder.",
                "Copy it from the van. Without it, photos can't be counted against the camera pulses or timed."))
        if not d.qinertia_projects:
            out.append(self.crew(ctx, Severity.WARN, None, "",
                f"No post-processed SBG (Qinertia) project was found for {d.day}.",
                f"No SBGData/{d.day}.<hhmmss>_0001 folder.",
                "Copy the day's Qinertia project folder(s) (SBGData\\<run>_0001) from the van."))
        if not d.camera_events and not any(rd.frame_lines for rd in d.runs.values()):
            out.append(self.crew(ctx, Severity.WARN, None, "",
                f"The camera log for {d.day} wasn't found.",
                f"No VideoLogCXP lines dated {d.day} in any day folder or the extra log folder.",
                "If the logs were copied somewhere else, choose that folder as the Log folder and check again."))
        if not d.offsets:
            if d.clock:
                out.append(self.note(ctx, None, "",
                    f"The SBG log for {d.day} wasn't found; photo times use the camera log instead.",
                    "No CallbackUtc lines; PC clock from FrameID lines (fallback)."))
            elif has_photos:
                out.append(self.crew(ctx, Severity.WARN, None, "",
                    f"Photo times can't be worked out for {d.day}: neither the SBG log nor the camera log was found.",
                    "No CallbackUtc lines and no FrameID lines.",
                    "Choose the folder holding the van's logs as the Log folder and check again."))
        for rd in ctx.checked_runs:
            if rd.has_image_dir and rd.sbg is None:
                out.append(self.crew(ctx, Severity.WARN, rd.run, "",
                    f"{cap(run_label(rd.run))}: its SBG DataLogger folder is missing, so its photos "
                    f"can't be counted against the camera pulses or timed.",
                    f"No SBGData/{yymmdd}/<run> DataLogger within ±{ctx.cfg.sbg_match_tolerance_s} s of {rd.run}.",
                    "Copy the run's DataLogger folder from the van."))
        return out
