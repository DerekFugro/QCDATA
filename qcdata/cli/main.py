"""`qcdata` command line. Thin layer: parse arguments, call the engine, write the
report through the add-only guard, print, and return the exit code."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from qcdata import __version__
from qcdata.config.locations import config_path
from qcdata.config.schema import ConfigError, load_config
from qcdata.core import engine
from qcdata.core.discovery import NotASignoffFolder, discover
from qcdata.core.model import Severity
from qcdata.core.paths import WriteGuard, WriteRefused
from qcdata.core.report import writer
from qcdata.core.report_data import build

EXIT_PASS, EXIT_WARN, EXIT_FAIL, EXIT_USAGE, EXIT_UNREADABLE = 0, 1, 2, 3, 4
EXIT_FOR = {Severity.PASS: EXIT_PASS, Severity.WARN: EXIT_WARN, Severity.FAIL: EXIT_FAIL}
DAY_RE = re.compile(r"^\d{8}$")

EPILOG = """examples:
  qcdata check F:\\
  qcdata check G:\\ --days all
  qcdata check D:\\copies\\17thAnd16th --days 20261016,20261017 --logs D:\\logs
  qcdata check F:\\ --json --no-report > findings.json

exit codes:
  0 PASS   1 NEEDS A LOOK (WARN)   2 PROBLEM FOUND (FAIL)
  3 bad usage or folder not found   4 folder can't be read or isn't a collection drive
"""


class UsageError(Exception):
    pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qcdata", description="Check a sidewalk collection drive for missing data.",
                                     epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"QCDATA {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="Print the QCDATA version and exit.")
    c = sub.add_parser("check", help="Check a drive or copied folder and write a report.",
                       epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    c.add_argument("target", help="Drive root (F:\\ or G:\\) or a copied folder with the same layout.")
    c.add_argument("--days", help="Comma-separated days (20261016,20261017) or 'all'. Default: the newest day.")
    c.add_argument("--logs", help="Extra folder to look in for the van PC's log files.")
    c.add_argument("--config", help="config.yaml to use (default: QCDATA_CONFIG, then the one beside the app).")
    c.add_argument("--json", action="store_true", help="Print the findings as JSON on stdout and nothing else.")
    c.add_argument("--quiet", action="store_true", help="Print nothing except errors (and --json output).")
    c.add_argument("--out", help="Put the report files in this folder instead of <target>\\_QCDATA. Still only adds files.")
    c.add_argument("--no-report", action="store_true", help="Don't write any files; just print the result.")
    return parser


def _parse_days(text: str | None, available: list[str]) -> list[str] | None:
    if text is None:
        return None
    if text.strip().lower() == "all":
        return available
    days = [d.strip() for d in text.split(",") if d.strip()]
    if not days:
        raise UsageError("--days is empty. Use e.g. --days 20261017 or --days all.")
    bad = [d for d in days if not DAY_RE.match(d)]
    if bad:
        raise UsageError(f"--days: {', '.join(bad)} isn't a day like 20261017.")
    missing = [d for d in days if d not in available]
    if missing:
        raise UsageError(f"--days: no data for {', '.join(missing)}. Days found: {', '.join(available) or 'none'}.")
    return sorted(set(days))


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _check(args) -> int:
    target = Path(args.target)
    if not target.exists():
        raise UsageError(f"The folder {target} doesn't exist.")
    if not target.is_dir():
        raise UsageError(f"{target} is a file, not a folder.")
    logs = Path(args.logs) if args.logs else None
    if logs is not None and not logs.is_dir():
        raise UsageError(f"The log folder {logs} doesn't exist.")
    if args.config and not Path(args.config).is_file():
        raise UsageError(f"The config file {args.config} doesn't exist.")
    try:
        cfg = load_config(config_path(args.config))
    except ConfigError as exc:
        raise UsageError(str(exc)) from exc

    say = (lambda m: None) if (args.quiet or args.json) else (lambda m: _err(m))
    try:
        manifest = discover(target, cfg, logs)
    except NotASignoffFolder as exc:
        _err(str(exc))
        return EXIT_UNREADABLE
    except OSError as exc:
        _err(f"Couldn't read {target}: {exc.strerror or exc}")
        return EXIT_UNREADABLE
    days = _parse_days(args.days, engine.available_days(manifest))

    say(f"Checking {target} ...")
    try:
        result = engine.run(target, cfg, days, logs)
    except NotASignoffFolder as exc:
        _err(str(exc))
        return EXIT_UNREADABLE
    except OSError as exc:
        _err(f"Couldn't read {target}: {exc.strerror or exc}")
        return EXIT_UNREADABLE
    if not result.days:
        _err(f"{target} has no days to check.")
        return EXIT_UNREADABLE

    when = datetime.now()
    data = build(result, when)
    written = None
    if not args.no_report:
        guard = WriteGuard(target, Path(args.out) if args.out else None)
        try:
            written = writer.write_reports(result, data, guard, when)
        except WriteRefused as exc:
            _err(str(exc))
        except OSError as exc:
            where = Path(args.out) if args.out else target
            _err(f"Couldn't save the report in {where} ({exc.strerror or exc}). The drive may be read-only. "
                 f"Nothing was written there. Run again with --out <another folder> to save the report.")

    if args.json:
        sys.stdout.write(writer.json_bytes(data).decode("utf-8"))
    elif not args.quiet:
        print(f"{data['overall_verdict_words']} - {data['target_name']}")
        for d in data["days"]:
            print(f"  {d['day']}: {d['verdict_words']} ({d['stats']['problems']} problem(s), "
                  f"{d['stats']['warnings']} warning(s), {d['stats']['runs_checked']} session(s) checked)")
        for item in data["what_to_do"]:
            print(f"  What to do: {item}")
        if written and written.html:
            print(f"Report: {written.html}")
    return EXIT_FOR[result.verdict]


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:          # argparse: --help/--version exit 0, bad usage exits 2
        return EXIT_PASS if exc.code == 0 else EXIT_USAGE
    if args.command == "version":
        print(f"QCDATA {__version__}")
        return EXIT_PASS
    try:
        return _check(args)
    except UsageError as exc:
        _err(str(exc))
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
