"""C8 - status-message warnings and errors, counted by code (technical section only).

A '9057 ... frames may get lost' is shown beside what the pulse check found for
that run: it is a warning, not proof of loss.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from qcdata.core.checks._pulses import photo_vs_pulses
from qcdata.core.checks.base import Check, register

_NUM = re.compile(r"\d+(\.\d+)?")


@register
class C08StatusMessages(Check):
    id, title = "C8", "Status-message warnings"

    def run(self, ctx):
        d = ctx.day
        msgs = [m for m in d.status if m.severity.lower() in ("warning", "error")
                or " ERR " in m.message or "type: WARN" in m.message]
        if not msgs:
            return []
        groups: Counter = Counter()
        runs_by_key: dict = defaultdict(set)
        for m in msgs:
            key = f"{m.code}" if m.code is not None else _NUM.sub("N", m.message)[:90]
            groups[(key, m.module)] += 1
            if m.run:
                runs_by_key[(key, m.module)].add(m.run)
        out = []
        for (key, module), n in sorted(groups.items(), key=lambda kv: (-kv[1], kv[0])):
            sample = next(m.message for m in msgs if (f"{m.code}" if m.code is not None
                                                      else _NUM.sub("N", m.message)[:90]) == key)
            out.append(self.note(ctx, None, module, f"{module}: “{sample[:120]}” — {n} time(s).",
                                 f"code/key={key} module={module} count={n}", count=n))
        # 9057 beside the pulse result
        for run in sorted(runs_by_key.get(("9057", "Video"), set())):
            rd = d.runs.get(run)
            if rd is None or rd.daily is None or not rd.daily.is_checked:
                continue                    # deleted or not-in-Daily runs aren't checked
            parts = []
            for view, seq in rd.photos.items():
                if seq is None:
                    continue
                r = photo_vs_pulses(rd, seq, d)
                if r is not None:
                    parts.append(f"{view}: {'no photos lost' if r.short == 0 else f'{r.short} photo(s) short'}")
            out.append(self.note(ctx, run, "",
                f"Run {run} logged “frames may get lost” (9057). Pulse check: "
                f"{'; '.join(parts) or 'not available'}.", ))
        return out
