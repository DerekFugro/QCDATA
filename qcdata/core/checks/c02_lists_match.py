"""C2 - the export log and the Daily list the same runs."""

from __future__ import annotations

from qcdata.core.checks.base import Check, register
from qcdata.core.model import Severity


@register
class C02ListsMatch(Check):
    id, title = "C2", "Export log and Daily agree"

    def run(self, ctx):
        d = ctx.day
        if d.daily is None or not d.export_found:
            return []
        in_daily = {r.run for r in d.daily.run_rows}
        in_export = {r for r, rd in d.runs.items() if rd.export_rows}
        only_export = sorted(map(str, in_export - in_daily))
        only_daily = sorted(map(str, in_daily - in_export))
        if not (only_export or only_daily):
            return []
        return [self.crew(ctx, Severity.WARN, None, "",
            "The export log and the Daily don't list the same runs.",
            f"In the export log only: {only_export or 'none'}. In the Daily only: {only_daily or 'none'}.",
            "Check that the day's export finished, and tell the office.",
            export_only=only_export, daily_only=only_daily)]
