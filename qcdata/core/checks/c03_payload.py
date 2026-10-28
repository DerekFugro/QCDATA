"""C3 - every checked run (Daily C or V) has its photo and laser folders.

Partial-copy guard: if most checked runs have NO payload at all, that is almost
certainly an incomplete copy, not lost data - so one WARN for the day replaces
one FAIL per run. Nothing is hidden: the runs are listed in the details.
"""

from __future__ import annotations

from qcdata.core.checks.base import Check, register, cap, rd_label
from qcdata.core.model import Severity


@register
class C03Payload(Check):
    id, title = "C3", "Photo and laser folders present"

    def run(self, ctx):
        runs = ctx.checked_runs
        if not runs:
            return []
        bare = [rd for rd in runs if not rd.has_image_dir and not rd.has_gocator_dir]
        out = []
        guard = len(bare) / len(runs) > ctx.cfg.partial_copy_threshold and len(bare) > 1
        if guard:
            out.append(self.crew(ctx, Severity.WARN, None, "",
                f"This day looks only partly copied — {len(bare)} of {len(runs)} runs have no photo "
                f"or laser data at all.",
                f"{len(bare)}/{len(runs)} checked sessions have neither Images/<run> nor GoCatorData/<run> "
                f"(partial-copy guard; threshold {ctx.cfg.partial_copy_threshold}).",
                "If you meant to copy the whole day, copy it again. If this is a partial sample, nothing is wrong.",
                suppressed_runs=[str(rd.run) for rd in bare]))
        for rd in runs:
            if guard and rd in bare:
                continue
            missing = []
            if not rd.has_image_dir:
                missing.append("photos")
            else:
                missing += [f"{v} photos" for v, seq in rd.photos.items() if seq is None]
            if not rd.has_gocator_dir:
                missing.append("laser files")
            if missing:
                what = " and ".join(missing)
                out.append(self.crew(ctx, Severity.FAIL, rd.run, "",
                    f"{cap(rd_label(rd))} has no {what}.",
                    f"{rd.run}: missing {', '.join(missing)} folder(s).",
                    "Copy this session's data from the van again. If it isn't on the van either, it was lost — tell the office."))
        return out
