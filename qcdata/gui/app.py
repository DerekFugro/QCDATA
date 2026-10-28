"""`qcdata-gui` entry point.

Phase 1 placeholder: the GUI is built in Phase 5. Exits with a clear message
so launch.bat can report it.
"""

from __future__ import annotations

import sys


def main() -> int:
    print("The QCDATA window is not built yet (it arrives in Phase 5).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
