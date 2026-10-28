"""C7 - runs on disk or in the status log with no Daily row: not part of the day."""

from __future__ import annotations

from qcdata.core.checks.base import Check, register


@register
class C07NotInDaily(Check):
    id, title = "C7", "Runs not in the Daily"

    def run(self, ctx):
        d = ctx.day
        if d.daily is None:
            return []
        extra = [rd for rd in d.runs.values() if rd.daily is None]
        if not extra:
            return []
        ids = sorted(str(rd.run) for rd in extra)
        return [self.note(ctx, None, "",
            f"{len(ids)} run(s) are on the drive but not in the Daily, so they aren't part of the day "
            f"(usually false starts): {', '.join(ids)}.",
            f"Runs with no Daily row: {ids}.", runs=ids)]
