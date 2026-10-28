"""Check interface, registry, and helpers shared by the checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

from qcdata.config.schema import Config
from qcdata.core.loader import DayData, DayTiming, RunData, time_day
from qcdata.core.model import CREW, EXPLAINED, TECHNICAL, Finding, RunId, Severity

REGISTRY: list["Check"] = []


@dataclass
class CheckContext:
    day: DayData
    cfg: Config
    _timing: DayTiming | None = field(default=None, repr=False)

    @cached_property
    def timing(self) -> DayTiming:
        return self._timing or time_day(self.day, self.cfg)

    @cached_property
    def checked_runs(self) -> list[RunData]:
        """Runs the Daily marks C or V - the only runs QCDATA checks."""
        return [rd for rd in self.day.runs.values() if rd.daily is not None and rd.daily.is_checked]


class Check:
    id: str = ""
    title: str = ""

    def run(self, ctx: CheckContext) -> list[Finding]:
        raise NotImplementedError

    # ---- helpers that build findings with this check's id
    def _f(self, ctx: CheckContext, severity: Severity, section: str, run: RunId | None,
           subject: str, plain: str, technical: str, what: str = "", **details) -> Finding:
        return Finding(self.id, severity, section, ctx.day.day, run, subject, plain, technical,
                       what, dict(details))

    def crew(self, ctx, severity, run, subject, plain, technical, what, **d) -> Finding:
        return self._f(ctx, severity, CREW, run, subject, plain, technical, what, **d)

    def note(self, ctx, run, subject, plain, technical="", **d) -> Finding:
        return self._f(ctx, Severity.PASS, TECHNICAL, run, subject, plain, technical or plain, "", **d)

    def explained(self, ctx, run, subject, plain, technical="", **d) -> Finding:
        return self._f(ctx, Severity.PASS, EXPLAINED, run, subject, plain, technical or plain, "", **d)


def register(cls):
    REGISTRY.append(cls())
    REGISTRY.sort(key=lambda c: int(c.id[1:]))
    return cls


def run_label(run: RunId, section: str | None = "") -> str:
    """How the crew names a run: 'session 20261017.142417 (section 315330)'.
    The section number comes from the Daily; left off when there isn't one."""
    sec = (section or "").strip()
    return f"session {run.value} (section {sec})" if sec else f"session {run.value}"


def rd_label(rd) -> str:
    """run_label for a RunData, taking the section from its Daily row."""
    return run_label(rd.run, rd.daily.section if rd.daily else "")


def cap(text: str) -> str:
    """Upper-case only the first letter (str.capitalize() would lower-case 'PM')."""
    return text[:1].upper() + text[1:]


SIDE_NAMES = {"L": "left laser", "R": "right laser"}
