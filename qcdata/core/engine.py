"""Run the checks for the chosen days and roll up a verdict.

One check crashing never stops the others: it becomes one FAIL naming the check,
so the crew always gets a report.
"""

from __future__ import annotations

import time
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from qcdata.config.schema import Config
from qcdata.core import explain
from qcdata.core.checks import REGISTRY, CheckContext
from qcdata.core.discovery import Manifest, discover
from qcdata.core.loader import DayData, DayTiming, load_days, time_day
from qcdata.core.model import CREW, TECHNICAL, Finding, Severity


@dataclass
class DayResult:
    day: str
    verdict: Severity
    findings: list[Finding]
    data: DayData
    timing: DayTiming
    stats: dict = field(default_factory=dict)


@dataclass
class CheckRun:
    target: Path
    manifest: Manifest
    days: dict[str, DayResult]
    verdict: Severity
    seconds: float


def available_days(m: Manifest) -> list[str]:
    days = set(m.days)
    days |= {r.day for r in m.image_runs} | {r.day for r in m.gocator_runs}
    return sorted(days)


def default_days(m: Manifest) -> list[str]:
    """The newest day only - a drive can hold many days."""
    days = available_days(m)
    return days[-1:] if days else []


def worst(severities) -> Severity:
    return max(severities, key=lambda s: s.rank, default=Severity.PASS)


def _cap(findings: list[Finding], limit: int) -> list[Finding]:
    groups: dict[tuple, list[Finding]] = defaultdict(list)
    for f in sorted(findings, key=lambda f: f.sort_key):
        groups[(f.check_id, f.section)].append(f)
    out: list[Finding] = []
    for (cid, section), fs in groups.items():
        if len(fs) <= limit:
            out += fs
            continue
        out += fs[:limit]
        rest = fs[limit:]
        sev = worst(f.severity for f in rest)
        out.append(Finding(cid, sev, section, fs[0].day, None, "",
                           f"…and {len(rest)} more like this.", f"{len(rest)} more {cid} findings capped.",
                           "", {"capped": len(rest)}))
    return out


def _stats(day: DayData, findings: list[Finding], ctx: CheckContext) -> dict:
    checked = ctx.checked_runs
    photos = sum(seq.count for rd in day.runs.values() for seq in rd.photos.values() if seq)
    stops = sum(len(f.details.get("stops", [])) for f in findings if f.check_id == "C16")
    c14 = next((f.details for f in findings if f.check_id == "C14" and "agreed" in f.details), None)
    return {
        "runs_in_daily": len(day.daily.run_rows) if day.daily else 0,
        "runs_checked": len(checked),
        "runs_deleted_by_crew": sum(1 for rd in day.runs.values() if rd.daily and rd.daily.status == "X"),
        "photos": photos,
        "stops": stops,
        "warnings": sum(1 for f in findings if f.section == CREW and f.severity is Severity.WARN),
        "problems": sum(1 for f in findings if f.section == CREW and f.severity is Severity.FAIL),
        "qc_video": c14,
        "daily_meta": dict(day.daily.meta) if day.daily else {},
    }


def check_day(day: DayData, cfg: Config) -> DayResult:
    ctx = CheckContext(day, cfg)
    findings: list[Finding] = []
    for check in REGISTRY:
        if not cfg.enabled(check.id):
            continue
        try:
            findings += check.run(ctx)
        except Exception as exc:  # noqa: BLE001 - one check must never stop the report
            tb = traceback.format_exception_only(type(exc), exc)[-1].strip()
            findings.append(Finding(check.id, Severity.FAIL, CREW, day.day, None, "",
                f"QCDATA couldn't finish one of its checks ({check.title}) for {day.day}.",
                f"{check.id} raised {tb}", "Send this report to the office so the problem can be fixed."))
    findings = explain.apply(day, findings)
    findings = sorted(_cap(findings, cfg.max_findings_per_check), key=lambda f: f.sort_key)
    verdict = worst(f.severity for f in findings if f.section == CREW)
    return DayResult(day.day, verdict, findings, day, ctx.timing, _stats(day, findings, ctx))


def run(target: Path, cfg: Config, days: list[str] | None = None, extra_log_dir: Path | None = None,
        *, read_lasers: bool = True) -> CheckRun:
    t0 = time.monotonic()
    manifest = discover(Path(target), cfg, extra_log_dir)
    chosen = sorted(days) if days else default_days(manifest)
    loaded = load_days(manifest, chosen, cfg, read_lasers=read_lasers)
    results = {d: check_day(loaded[d], cfg) for d in chosen}
    return CheckRun(Path(target), manifest, results, worst(r.verdict for r in results.values()),
                    time.monotonic() - t0)


# Convenience for tests and the report: findings split by section.
def by_section(result: DayResult) -> dict[str, list[Finding]]:
    out: dict[str, list[Finding]] = {"crew": [], "explained": [], "technical": []}
    for f in result.findings:
        out.setdefault(f.section, []).append(f)
    return out


__all__ = ["CheckRun", "DayResult", "available_days", "by_section", "check_day", "default_days", "run",
           "worst", "TECHNICAL"]
