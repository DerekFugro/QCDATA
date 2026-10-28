"""C14 - verify QC_Video.csv against QCDATA's own tail check (C6's arithmetic).

QC_Video rows mean "the photos stop before the run's recorded end": First File is
the last photo that exists; Last File is the end distance written as a fake file
name. QCDATA re-derives the same thing and reports any disagreement.
"""

from __future__ import annotations

from qcdata.core.checks.base import Check, register, rd_label
from qcdata.core.checks.c06_tail import tail_shortfall_m
from qcdata.core.model import Severity

END_TOLERANCE_M = 0.05


def _num(name: str) -> int | None:
    stem = name.rsplit(".", 1)[0]
    return int(stem) if stem.isdigit() else None


@register
class C14QcVideo(Check):
    id, title = "C14", "QC_Video verified"

    def run(self, ctx):
        d, t = ctx.day, ctx.cfg.thresholds
        if d.qc_video is None:
            return [self.note(ctx, None, "", f"No QC_Video.csv for {d.day}, so it couldn't be verified.")]
        rows = {(r.run, r.view.lower()): r for r in d.qc_video}
        out, compared, agreed = [], 0, 0
        seen = set()
        for rd in d.runs.values():
            checked = rd.daily is not None and rd.daily.is_checked
            for view, seq in rd.photos.items():
                end, short = tail_shortfall_m(rd, seq)
                if end is None or end == 0:
                    continue
                key = (rd.run, view.lower())
                seen.add(key)
                qv = rows.get(key)
                ours = short > t.c6_warn_m
                compared += 1
                problem = None
                if qv and ours:
                    same_last = _num(qv.first_file) == seq.names_mm[-1]
                    qv_end = _num(qv.last_file)
                    same_end = qv_end is not None and abs(qv_end / 1000 - end) <= END_TOLERANCE_M
                    if same_last and same_end:
                        agreed += 1
                    else:
                        problem = (f"QC_Video and QCDATA both find missing photos at the end of "
                                   f"{rd_label(rd)} ({view}), but disagree on where.",
                                   f"QC_Video first/last {qv.first_file}/{qv.last_file}; QCDATA last photo "
                                   f"{seq.names_mm[-1]:012d}, end {end:.3f} m.")
                elif qv and not ours:
                    problem = (f"QC_Video lists missing photos at the end of {rd_label(rd)} ({view}), "
                               f"but QCDATA finds the photos reach the end.",
                               f"QC_Video row {qv.first_file}..{qv.last_file} n={qv.image_count}; QCDATA "
                               f"shortfall {short:.2f} m.")
                elif ours and not qv:
                    problem = (f"QCDATA finds the photos stop {short:.1f} m short at the end of "
                               f"{rd_label(rd)} ({view}), but QC_Video doesn't list it.",
                               f"QCDATA shortfall {short:.2f} m; no QC_Video row.")
                else:
                    agreed += 1
                if problem:
                    if checked:
                        out.append(self.crew(ctx, Severity.WARN, rd.run, view, problem[0], problem[1],
                                             "Tell the office — QC_Video and QCDATA disagree about this session."))
                    else:
                        out.append(self.note(ctx, rd.run, view, problem[0], problem[1]))
        unverifiable = sorted(str(k[0]) + "/" + k[1] for k in rows if k not in seen)
        if unverifiable:
            out.append(self.note(ctx, None, "",
                f"{len(unverifiable)} QC_Video row(s) couldn't be checked because those photos aren't on "
                f"this drive.", f"Unverifiable QC_Video rows: {unverifiable}", rows=unverifiable))
        out.append(self.note(ctx, None, "",
            f"QC_Video agreed with QCDATA on {agreed} of {compared} session-camera pairs "
            f"({len(d.qc_video)} row(s) in QC_Video.csv).",
            f"C14 agreed={agreed} compared={compared} qc_video_rows={len(d.qc_video)}",
            agreed=agreed, compared=compared, qc_video_rows=len(d.qc_video)))
        return out
