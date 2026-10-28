# QCDATA

Checks a sidewalk collection drive (`F:\` or `G:\`, or a copied folder with the
same layout) for missing or incomplete data — photos, lasers, SBG, logs — and
writes a plain-language report: **PASS**, **NEEDS A LOOK**, or **PROBLEM FOUND**.

QCDATA only reads the drive. The one thing it adds is a `_QCDATA` folder with the
report files in it. It never changes, moves or deletes anything, and it never
overwrites an earlier report.

**Status:** Phases 1–4 done (parsers, checks, report, command line). The window
for the crew arrives in Phase 5.

## What it checks

The day's **Daily** (`<day>\Daily_*.csv`) decides which runs count:

| Daily status | What QCDATA does |
|---|---|
| `C` collected, `V` verification | Fully checked |
| `X` deleted | Not checked — listed under "Explained by the crew" |
| no Daily row | Not part of the day (noted for the office) |

For every checked run it confirms photos (ROW and Rear), both laser files, the
SBG DataLogger, the export run list and the status messages are there and agree;
counts each photo against the GPS camera pulses (`eventOutA`) to find dropped
photos; and re-checks `QC_Video.csv`. The full list of checks is in
`Specs/QCDATA_Instructions.md`.

## The report files

Each check adds three new files to `<drive>\_QCDATA\` (or the `--out` folder):

| File | What it is |
|---|---|
| `QCDATA_Report_<name>_<YYYYMMDD-HHMMSS>.html` | The report the crew opens. One file, works offline, prints in black and white. |
| `findings_<name>_<YYYYMMDD-HHMMSS>.json` | The same findings for scripts. |
| `images_<name>_<YYYYMMDD-HHMMSS>.csv` | Every photo with its time (see below). |

`<name>` is the folder name, or for a drive root its volume label. If a file with
that name already exists, QCDATA adds `-2`, `-3`, … instead of overwriting.

If the drive is read-only, nothing is written there; QCDATA says so. Run again
with `--out <another folder>`.

### The per-photo list

One row per photo file: `day, run, view, filename, photo_number, pulse_number,
pulse_device_us, gps_utc, pc_time, local_time, time_source, gap_from_previous_s,
flags`. No time comes from a file date (copying destroyed those).

- `gps_utc` — the GPS time of the camera trigger pulse (about 1 ms).
- `pc_time` — that moment on the van PC's clock: the closest thing to the
  photo's original creation time (about 0.1 s).
- `time_source` — `pulse`, `startup_frame` (photo 1, taken before the first
  pulse), `unverified`, or `none`.

The first few lines start with `#` and explain the columns. In Excel the column
headings are on the row after them.

## Command line

```
qcdata check <drive_or_folder> [--days 20261016,20261017 | --days all]
                               [--logs PATH] [--config PATH] [--json] [--quiet]
                               [--out PATH] [--no-report]
qcdata version
```

| Option | Meaning |
|---|---|
| `--days` | Which days to check. Default: the newest day on the drive. `all` checks every day. |
| `--logs` | An extra folder to look in for the van PC's log files, when they aren't in the day folder. |
| `--config` | The settings file to use. |
| `--json` | Print the findings as JSON on stdout and nothing else, so it can be piped. Report files are still written unless `--no-report`. |
| `--quiet` | Print nothing except errors. |
| `--out` | Save the report files in this folder instead of `<drive>\_QCDATA`. Still only adds files. |
| `--no-report` | Don't write any files. |

There is no option to overwrite anything.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | PASS |
| `1` | NEEDS A LOOK (WARN) |
| `2` | PROBLEM FOUND (FAIL) |
| `3` | Bad usage, or the folder doesn't exist |
| `4` | The folder can't be read, or isn't a collection drive |

WARN and FAIL are separate so a script can treat warnings as advisory. If the
report couldn't be saved (read-only drive), the exit code is still the verdict
and the reason is printed on stderr.

Examples:

```
qcdata check F:\
qcdata check G:\ --days all
qcdata check D:\copies\17thAnd16th --days 20261016,20261017 --logs D:\logs
qcdata check F:\ --json --no-report > findings.json
```

## Settings (`config.yaml`)

Where the settings come from, first match wins: `--config`, then the
`QCDATA_CONFIG` environment variable, then `config.yaml` beside the app, then the
built-in defaults. Any key left out uses its default; an unknown key is an error
(so a typo is caught).

| Key | Default | Meaning |
|---|---|---|
| `data_drives` | `["F:", "G:"]` | Drive letters collection drives show up on. |
| `folders.images` | `Images` | Photo folder at the drive root. |
| `folders.gocator` | `GoCatorData` | Laser folder at the drive root. |
| `folders.sbg` | `SBGData` | SBG folder at the drive root. |
| `pc_names` | `[ARAN01-SERVER, ARANSW1-SERVER]` | PC names in ACS log file names. |
| `local_timezone` | `America/New_York` | Time zone for `local_time` in the photo list. |
| `tai_minus_utc_s` | `37` | Laser `ptpTimestamp` is TAI; this converts it to UTC. |
| `sbg_match_tolerance_s` | `2` | A DataLogger folder may be named up to this many seconds off its run. |
| `expected_step_mm` | `750` | Photo spacing, as a cross-check (the real step is worked out per run). |
| `partial_copy_threshold` | `0.5` | If more than this share of runs has no payload, report one "partly copied" warning instead of one per run. |
| `max_findings_per_check` | `500` | After this many findings from one check, the rest become "…and N more like this." |
| `checks.C1` … `checks.C17` | `true` (C13 `false`) | Turn a check on or off. C13 (database) arrives in Phase 6. |
| `thresholds.c6_warn_m` | `3.0` | Photos stop this many metres short of the run's end → NEEDS A LOOK. |
| `thresholds.c6_fail_m` | `8.0` | … this many metres → PROBLEM FOUND. |
| `thresholds.c10_max_abs_diff` | `25` | Left and right laser row counts may differ by this many rows … |
| `thresholds.c10_max_pct_diff` | `1.0` | … or this percent, whichever is larger. |
| `thresholds.laser_short_pulses` | `2` | Pulses (0.75 m each) a laser may miss at the start or end before it is reported. |
| `thresholds.min_pulse_gap_s` | `0.13` | A pulse closer than this to the previous one gets no photo (normal). |
| `thresholds.normal_end_short` | `2` | Photos short at the end of a run that are normal. |
| `thresholds.stop_s` | `5.0` | A gap between pulses this long counts as a stop. |
| `thresholds.clock_drift_note_s` | `2.0` | PC-vs-GPS clock drift within a day worth noting for the office. |
| `thresholds.frame_log_tolerance_s` | `0.1` | Photo-time self-check: allowed difference from the day's usual camera-log delay. |

## Development

- Double-click `launch.bat` (sets up the environment with `uv` on first run).
- `uv run qcdata check <folder>` · `uv run pytest`
- Tests that use real data read `QCDATA_SAMPLE_ROOT` (default
  `F:\001_BuggyData\001_RawData\100_Signoff`) and skip if it isn't there.

The spec is in `Specs/QCDATA_Instructions.md`; the build plan in
`Specs/QCDATA_Phase.md`; orientation in `CONTEXT.md`.
