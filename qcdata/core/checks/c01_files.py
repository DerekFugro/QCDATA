"""C1 - the day's own files: Daily, run list, status messages; payload with no day folder."""

from __future__ import annotations

from qcdata.core.checks.base import Check, register
from qcdata.core.model import Severity


@register
class C01Files(Check):
    id, title = "C1", "Day files present"

    def run(self, ctx):
        d, out = ctx.day, []
        if d.folder is None:
            out.append(self.crew(ctx, Severity.WARN, None, "",
                f"Photos or laser files were found for {d.day}, but there is no {d.day} folder.",
                f"Payload runs exist for {d.day} but no day folder was found at the root.",
                f"Copy the {d.day} folder from the van, then check again."))
            return out
        if d.daily is None:
            out.append(self.crew(ctx, Severity.FAIL, None, "",
                f"The Daily file for {d.day} is missing, so QCDATA can't tell which runs were collected.",
                f"No Daily_*_{d.day}.csv in {d.folder.path}.",
                f"Copy the Daily file (Daily_ARAN01_{d.day}.csv) into the {d.day} folder, then check again."))
        if not d.export_found:
            out.append(self.crew(ctx, Severity.WARN, None, "",
                f"The export log for {d.day} wasn't found.",
                f"No run list (header 'UniqueRun,...') with sessions from {d.day} in the day folder, "
                f"ExportBakFiles, or the extra log folder.",
                "If the logs were copied somewhere else, choose that folder as the Log folder and check again."))
        if d.folder.status_messages is None:
            out.append(self.note(ctx, None, "", f"No status-message file for {d.day}.",
                                 f"No *_StatusMessages_{d.day}.csv in {d.folder.path}."))
        return out
