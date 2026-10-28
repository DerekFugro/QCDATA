"""`qcdata` command-line entry point.

Phase 1: only `qcdata version` works. `qcdata check` arrives in Phase 4.
"""

from __future__ import annotations

import argparse
import sys

from qcdata import __version__

EXIT_BAD_USAGE = 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qcdata",
        description="Check a sidewalk collection drive for missing data.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="Print the QCDATA version and exit.")
    check = sub.add_parser("check", help="Check a drive or folder (not built yet).")
    check.add_argument("target", help="Drive root (F:\\ or G:\\) or a copied folder.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "version":
        print(f"QCDATA {__version__}")
        return 0
    if args.command == "check":
        print("qcdata check is not built yet (it arrives in Phase 4).", file=sys.stderr)
        return EXIT_BAD_USAGE
    return EXIT_BAD_USAGE


if __name__ == "__main__":
    sys.exit(main())
