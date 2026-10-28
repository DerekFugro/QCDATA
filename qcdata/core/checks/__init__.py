"""The checks. Each module registers one Check; the engine runs them in ID order."""

from qcdata.core.checks.base import REGISTRY, Check, CheckContext  # noqa: F401
from qcdata.core.checks import (  # noqa: F401  (import = register)
    c01_files, c02_lists_match, c03_payload, c04_cameras_match, c05_photo_holes,
    c06_tail, c07_not_in_daily, c08_status_messages, c09_gps_mode, c10_lasers,
    c11_parts, c14_qc_video, c15_pulses, c16_stops, c17_time_sync,
)
