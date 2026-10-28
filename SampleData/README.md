# Sample data - not copied here

The real sample data is 13 GB, so it stays where it is and is read in place,
read-only:

    F:\001_BuggyData\001_RawData\100_Signoff

| Folder | Use |
|---|---|
| `17thAnd16th\` | Reference layout. `20261017` = reference day. `20261016` = 44 runs marked X by the crew (explained), 4 complete runs. |
| `Zipfiles\Batch1\` | Multi-day reference (six days; Oct 15 has no export log; Oct 16 exported twice). |
| `20261009_*Reverse*` | Positive QC_Video case (28 real tail losses with photos present). |

Tests that need real data read the path from the `QCDATA_SAMPLE_ROOT`
environment variable (default above) and are **skipped** if it isn't there, so
the test suite still runs on a machine without the drive.

Never write anything into these folders.
