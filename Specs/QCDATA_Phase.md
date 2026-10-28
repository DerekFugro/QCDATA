---
# Implementation Plan for QCDATA

> Gated phases. After each phase, run the full test suite, report results, and
> wait for "proceed". Do not advance if any test fails. Each phase must leave the
> codebase in a runnable state. The proceed decision is made at the strongest
> model tier (see the routing table at the end).
>
> Read `QCDATA_Instructions.md` first. This file is the build order; that file is
> the contract. Where they appear to disagree, the Instructions win — stop and
> raise it.

**Eight phases. Phase 6 is blocked on information Derek does not yet have, and
Phase 8 is partly blocked (needs the fuller dataset). Phases 1–5 can be built end to end today and
produce a working, shippable app without the database check.**

---

## Phase 1 — Environment Setup
**Complexity:** Simple
**Goal:** A `uv`-managed Python 3.13 project with the house layout, a green empty
test suite, and a `launch.bat` that runs. No application logic.

### Dependencies
| Tool / Library | Version | Purpose |
|----------------|---------|---------|
| Python | 3.13.x | Runtime (`requires-python = ">=3.13,<3.14"`) |
| uv | latest | Environment and lockfile manager — not pip, not conda |
| PySide6-Essentials | 6.11.3 | Installed now, first used in Phase 5 (core Qt modules only — no Addons) |
| Jinja2 | 3.1.6 | Installed now, first used in Phase 4 |
| PyYAML | >=6,<7 | `config.yaml` |
| defusedxml | latest | Safe XML parsing of the settings file |
| pytest | 9.2.0 | Test framework (dev group) |
| pip-audit | latest | Vulnerability audit (dev group) |

Do **not** add `pyodbc` yet — it arrives in Phase 6. Do **not** add pandas or
numpy at all; see the Instructions for why.

### Tasks
1. Read `CONTEXT.md`, the three standards files in `Specs/`, and
   `..\ImageQC\CONTEXT.md` / `pyproject.toml` / `launch.bat` for house conventions.
2. Web-search to confirm the versions above are still current; report any drift
   before installing.
3. Create the package skeleton:
   ```
   qcdata/
     __init__.py
     core/   __init__.py        <- UI-free engine (no Qt imports, ever)
     cli/    __init__.py
     gui/    __init__.py
     config/ __init__.py
   tests/
   Specs/            (already populated)
   SampleData/
   Reference/
   ```
4. Write `pyproject.toml` modelled on `ImageQC`'s: hatchling build, `packages = ["qcdata"]`,
   `[project.scripts] qcdata = "qcdata.cli.main:main"`,
   `[project.gui-scripts] qcdata-gui = "qcdata.gui.app:main"`,
   `[tool.pytest.ini_options] testpaths = ["tests"]`, comments on every pin.
5. `uv sync`; commit `uv.lock`.
6. Write `launch.bat` following `..\ImageQC\launch.bat` — uv presence check,
   first-run `uv sync`, then `uv run qcdata-gui`, with pauses on error.
7. Write `.gitignore` (`.venv/`, `.env`, `__pycache__/`, `_QCDATA/`, SampleData
   payload) and `.env.example` (keys, no values — DB keys for Phase 6).
8. Copy the sample data into `SampleData\17thAnd16th\` **read-only**, or document
   the source path if it is too large to copy. Keep the 2026-10-17 day in full —
   the tests need it.
9. One placeholder test asserting the package imports. Confirm `pytest` is green.

### Done when:
- [ ] `uv sync` completes clean and `uv.lock` is committed.
- [ ] `uv run pytest` is green (1 trivial test).
- [ ] `launch.bat` runs and fails gracefully with a clear message (no GUI yet).
- [ ] `uv run qcdata version` prints a version (stub `main` is fine).
- [ ] A version summary of every installed package is reported.
- [ ] `qcdata/core/` contains no Qt import, verified by grep.

---

## Phase 2 — Parsers and the data model
**Complexity:** Moderate
**Goal:** Turn a signoff folder into typed Python objects. **Pure reading, zero
judgment** — no check logic, no verdicts. This phase is where the format rules
live, and getting it right makes every later phase easy.

### Dependencies
No new packages. Uses stdlib `csv`, `pathlib`, `re`, `statistics`, `collections`,
plus `defusedxml` and `PyYAML` from Phase 1.

### Tasks
1. **`core/model.py`** — dataclasses, all frozen where practical:
   - `SessionId` — normalizes `[20261017.153218]` and `20261017.153218` to one
     canonical form. One parse function, used everywhere:
     `^\[?(\d{8}\.\d{6})\]?$`. This type is the join key for the whole app.
   - `ExportedRun` — session, section name, begin/end distance stamp, begin/end
     chainage.
   - `DailyRow` — session, section, functional class, GPS mode, date, comments,
     and the measurement columns (keep them; C9 needs GPS mode, later checks may
     want more).
   - `StatusMessage` — session, severity, message, module, timestamp, distance
     stamp, and a parsed `code` (the leading integer of messages like
     `9057 - Camera ROW ...`, `None` when absent).
   - `ImageSequence` — session, view (`ROW`/`Rear`), sorted frame distances in mm,
     `derived_step`, `first_mm`, `last_mm`, `missing_mm` list.
   - `GoCatorPair` — session, L row count, R row count, both file paths.
   - `DayData` — everything above for one day folder, plus the payload session
     sets and the lists of collected / not-collected sections.
   - `Finding` — `check_id`, `severity` (enum `PASS`/`WARN`/`FAIL`), `session`,
     `message_plain`, `message_technical`, `what_to_do`, `details` dict.
2. **`core/discovery.py`** — given a drive root (`F:\`, `G:\`) or a copied folder
   of the same shape, find the day folders
   (`^\d{8}$`), locate `Images/`, `GoCatorData/`, `SBGData/`, and return a
   manifest. Must handle: more than one day folder in a signoff folder; a missing
   payload folder; a folder that is not a signoff folder at all (clear error, not
   a traceback). Payload folder names come from `config.yaml` (`folders:`), matched
   ignoring case (defaults `Images`, `GoCatorData`, `SBGData`). At a drive root, ignore
   `$RECYCLE.BIN`, `System Volume Information`, and unrelated folders. Export
   run lists come from the day folder, `ExportBakFiles\`, and the optional extra
   log folder, often duplicated across them, and are told apart from export
   process logs (`ExportLogs\*_export_log.csv`) by their header; photos may be `.JPG` or `.jpg`. Search those
   places; don't assume one. The standard layout is `Zipfiles\Batch1`'s (see Instructions,
   "The standard signoff layout"); non-standard folders get a clear message, not
   support.
3. **`core/parsers/export_log.py`** — glob `ARAN01_Export_*_log.csv`, skip the
   three-line preamble (title, Start Date, End Date — capture the dates), parse
   rows into `ExportedRun`. Note the trailing-comma habit in these CSVs: every
   row ends with `,`, so expect a trailing empty field and do not treat it as a
   column.
4. **`core/parsers/daily.py`** — `Daily_ARAN01_*.csv`. Row 1 is the header, **row
   2 is a blank spacer row** — skip it. Read every column by header name, never
   by index. Parse `Status` (`C` and `V` = check, `X` = don't check, anything else =
   unknown), classify
   `Comments` by prefix (`Delete File -`, `Section Collected Short -`, `Other -`)
   while keeping the full text, and turn the **footer rows** (`ACS Version ...`,
   `Daily Report Version ...`, `Time in motion - ...`) into metadata. A row
   without a valid session id is never a session; a `[0]` row is listed but never
   joined.
5. **`core/parsers/status.py`** — `ARAN01_StatusMessages_*.csv`. Stream it (1.1 MB
   on one sample day, and it can be much larger). Extract the message code.
   Note: a sibling zero-byte file (`ARAN01_StatusMessages_<date> 6005 -.csv`) was
   present in the samples — glob must not pick it up; match the exact
   `ARAN01_StatusMessages_<YYYYMMDD>.csv` form.
6. **`core/parsers/images.py`** — the most important parser.
   - List `Images/<session>/<view>/*.jpg`; parse each name as a 12-digit
     millimetre distance.
   - **Derive the step** as the modal difference between consecutive sorted
     distances. Do not hard-code 750.
   - Compute `missing_mm` as the multiples of the derived step between first and
     last that have no file.
   - Never open an image. Directory listing only — a day has ~12 000 of them.
7. **`core/parsers/gocator.py`** — per run and side, `<run with T>L.csv` /
   `R.csv`: missing vs empty (no profile rows) vs present, row count, `frameIndex`
   gaps, first/last `ptpTimestamp` (ignoring jumps in the first rows while PTP
   locks). Read only the first four columns of each row — rows are tens of kB.
   `ptpTimestamp` is TAI from the SBG: UTC = ptp − `tai_minus_utc_s` (37). See
   Instructions, "Lasers".
8. *(Removed: the Morning / Mid-Day / Evening sample photos and receipts don't
   matter — only the root `Images\` folder does.)*
9. **`core/parsers/settings.py`** — parse `ARAN01_Settings_*.xml` with
   `defusedxml`. Minimal for now: confirm it parses and extract a few identifying
   fields. Do not build settings comparison — that is `ProjectCompare`'s job.
9a. **`core/parsers/sbg.py`** — per run's `<id> DataLogger` folder, matched to
   the run within ±2 s:
   - `eventOutA.txt` (and `eventOutB`, `eventInA` for the cross-check) → device
     times in µs. **Parse with `line.split()`; accept any row whose first token is
     an integer** — timestamps are right-aligned with leading spaces. **Unwrap the
     32-bit counter** (rolls over every 4 294.967 296 s). Both bugs were hit during
     spec research; each needs a regression test (`170358` is the rollover case).
   - `utcTime.txt` → (device µs, UTC) pairs, same unwrap, for interpolation.
   - Read **only** these files from each DataLogger folder. Stream them.
   - Also list `SBGData/<id>_0001` Qinertia projects per day, and try to read
     each one's time span (e.g. `job.json`) — see the reference gap on Qinertia
     coverage.
9a2. **`core/parsers/logs.py`** — ACS logs from `<day>/Logs/<PC>/`, every day
   folder, and the extra log folder: both PC names (`ARAN01-SERVER`,
   `ARANSW1-SERVER`), any case; all rotations (`.log`, `.log.N`); every line
   filtered by date. Extract: camera-log `VC2_StartAcquisition` /
   `VC2_StopAcquisition` times and `FrameID` lines (PC time, frame number, run,
   view, file, `MilErr`); SBG-log `CallbackUtc` offsets. Stream; logs reach 20 MB
   and there are dozens.
9b. **`core/parsers/qc_video.py`** — `QC_Video.csv`, with or without a trailing
   comma on the header, with an optional 9th note column. `First File` is the
   last existing image; `Last File` is a distance encoded as a filename;
   chainages are kilometres. See the Instructions.
9c. **Photo times** (`core/photo_times.py`) — photo `k` ↔ pulse `k − 1` (photo 1
   is the start-up frame — confirmed by Derek and by the FrameID lines);
   pulse → GPS time via `utcTime`; GPS → PC time via the day's offset (`SBG.log`,
   else FrameID fallback); FrameID self-check per run. See Instructions, "Photo
   times".
10. **`config/schema.py` + `config.yaml`** — load with `yaml.safe_load`, validate
    against an explicit schema with defaults, reject unknown keys with a clear
    message. Every threshold from the Instructions goes here with its documented
    default.

### Tasks — fixtures
11. **`tests/fixtures.py`** — a builder that writes a synthetic signoff folder
    into `tmp_path`: N sessions, chosen frame distances, chosen status messages,
    chosen L/R row counts. Every later phase's tests depend on this, so build it
    properly now. It must be able to produce: a clean day, a day with an injected
    frame gap, a 48/4 partial-copy day, and a malformed-CSV day.

### Done when:
- [ ] Parsing the real `SampleData\17thAnd16th` yields, for 2026-10-17: **28**
      exported runs, **28** daily rows, **30** sessions in status messages,
      **30** image session folders, **30** GoCator session folders.
- [ ] For 2026-10-16: **48** exported runs, **48** daily rows, **4** image session
      folders.
- [ ] Derived step is **750 mm** for every session on both days.
- [ ] `Zipfiles\Batch1`: all six day folders found; export rows for 10/09,
      10/10, 10/14, 10/16 (2 exports, 48 runs — the morning's 2 re-exported) and
      10/17 collected from the day folders and `ExportBakFiles` with no
      duplicates; the 4 `ExportLogs` files recognised as process logs; 10/15 has
      none; payload assigned to days by session-id date.
- [ ] Daily for 2026-10-17: **25** `C`, **3** `X` (`142650`, `160558`,
      `161445`), footer parsed as metadata (`ACS Version 2.6.5.774`, time in
      motion `2h 0m 24s`).
- [ ] SBG for 2026-10-17: all **30** image sessions matched to an SBG folder,
      including the 1-second-late `154209` and `154928`. (`141947` and `160558`
      have 0 triggers and 1 image each — consistent with the +1 rule.) Unmatched
      SBG folders `151624` and `163727` listed.
- [ ] Pulse counts for 2026-10-17 equal (photo count − 1) in all 30 runs once the
      `154422` no-photo pulse (< 0.13 s) is dropped.
- [ ] `170358`'s counter rollover is unwrapped.
- [ ] PC-vs-GPS offset for 2026-10-17 read from `SBG.log` as 3651.555 s, PC
      ahead; the FrameID fallback gives the same within 0.2 s.
- [ ] Every FrameID line on 2026-10-17 matches its computed PC time within 0.5 s.
- [ ] Lasers on 2026-10-17: none missing, `160558` L and R empty, no `frameIndex`
      gaps in any file; on both sides no pulses after the last laser row, and none
      before the first except `154208` (one pulse, both sides).
- [ ] `QC_Video.csv` parses for every folder in the corpus, including the
      2026-10-20 copy with the note column.
- [ ] `SessionId` round-trips bracketed and unbracketed forms; tested.
- [ ] Parsers are tested against fixtures *and* against the real sample folder.
- [ ] A malformed CSV row produces a logged skip, not an exception.
- [ ] No image file is ever opened (assert via a monkeypatched `open`, or review).
- [ ] `qcdata/core/` still has no Qt import.
- [ ] Full test suite green.

---

## Phase 3 — The check engine
**Complexity:** Complex
**Goal:** C1–C11 and C14–C17 implemented behind one interface, the partial-copy
guard, the explained-findings rule, the verdict roll-up, the JSON output, and the
per-image inventory data. **This is the heart of the app** — the GUI and report
are presentation over this.

### Dependencies
No new packages.

### Tasks
1. **`core/checks/base.py`** — the `Check` interface:
   `check_id`, `title`, `enabled_by_default`, and
   `run(day: DayData, cfg: Config) -> list[Finding]`. Plus a registry so checks
   are discovered rather than hand-listed in a long if-chain.
2. **One module per check**, C1 through C11 and C14 through C17, exactly as
   tabulated in the Instructions. Each is independently enable/disable-able from
   `config.yaml`. C16 and C17 never raise the verdict; C17 never appears in the
   crew section.
2a. **The explained-findings rule** (`core/explain.py`) — applied by the runner
   *after* checks emit findings and *before* the verdict roll-up. Runs the Daily
   marks `X` are not checked and are listed under "Explained by the crew"; a run
   whose comment contains `Section Collected Short` has its C6 finding moved there
   at PASS. Runs with no Daily row are not part of the day (technical section).
   `V` runs are checked like `C`. Explained findings stay visible; they never raise the verdict.
2b. **Per-photo list** (`core/inventory.py`) — one record per photo file, with
   the columns given in the Instructions ("Photo times"): day, run, view, photo
   and pulse numbers, GPS time, PC time, local time, `time_source`, gap, flags.
   Never uses a file date.
3. **Per-check exception isolation** — the runner wraps each check; an unexpected
   exception becomes a FAIL finding naming that check, and the remaining checks
   still run. The crew always gets a report. Test this with a deliberately
   throwing check.
4. **The partial-copy guard** (`core/engine.py`) — compute the no-payload fraction
   before emitting C3 findings; above `partial_copy_threshold` (default 0.5),
   suppress the per-session C3 findings and emit one day-level WARN with the
   wording given in the Instructions. Retain the suppressed list in
   `Finding.details` so nothing is lost, only de-emphasized.
5. **C6 zero-end special case** — `EndDistanceStamp == 0` with any photos
   present is its own WARN (unless the Daily explains it) and must not reach the
   tolerance arithmetic.
6. **C8 aggregation** — group status messages by code; one technical-section
   line per code with a count. C8 never raises the verdict. Show each `9057`
   beside that run's C15 result ("no photos lost" or the loss C15 found).
7. **Finding caps** — at most `max_findings_per_check` (default 500) retained;
   beyond that, append "and N more".
8. **Verdict roll-up** — worst severity across all findings becomes the day
   verdict. Define it once, in one function.
9. **`core/report_data.py`** — the JSON structure the report and CLI both render
   from. Deterministic key and list ordering (sort findings by check id, then
   session) so two runs on unchanged data are byte-identical apart from the
   timestamp.
10. **The write-path guard** (`core/paths.py`) — one function owns all writes.
    Resolve with `Path.resolve()`; allow only `<signoff>/_QCDATA/` and the app's
    own `config.yaml` and `qcdata_state.json`; refuse everything else.
    Reject `..`, outward symlinks, and absolute paths from config.

### Done when:
- [ ] All fifteen checks (C1–C11, C14–C17) implemented, registered, and
      individually toggleable.
- [ ] **Reference day 2026-10-17 → PASS.** No crew-section warnings or failures.
      `142650`, `160558`, `161445` under "Explained by the crew". Technical
      section: `141947` and `154142` (no Daily row), the `154422` no-photo pulse,
      `154208`'s one-pulse late laser start (both sides), the `9057` rows beside
      "no photos lost" for `165541`, `NoSolution`, the stops, and the PC offset
      and drift.
- [ ] C14 on both 2026-10-09 reverse-run folders: zero disagreements across all
      28 session-views with images.
- [ ] C14 on every folder where `QC_Video.csv` is empty: nothing to report.
- [ ] `test_c15_extra_photos_fail`, `test_c15_start_short_warns`,
      `test_c15_end_short_two_is_normal` pass.
- [ ] `test_daily_x_sessions_are_explained` passes.
- [ ] Inventory has exactly one record per image file for the reference day.
- [ ] **Synthetic partial day** (48 `C` runs, 4 with photos) → exactly one
      day-level partial-copy WARN, not 44 C3 findings.
- [ ] **Real 2026-10-16** → WARN with exactly 2 C6 + 2 C10 (run `172652`, quoting
      its "Delete File" comment) + 1 C11 (no Qinertia project); its 44 `X` runs under
      "Explained by the crew".
- [ ] `test_c5_detects_injected_gap` passes, and the reported missing distance is
      the exact value deleted.
- [ ] `165541`'s `9057` rows sit in the technical section beside "no photos lost"
      (in `test_reference_day_verdict`); the verdict stays PASS.
- [ ] `test_c6_zero_end_is_special_cased` passes.
- [ ] `test_c8_aggregates_by_code` passes — 104 `9056` rows produce one finding.
- [ ] `test_c10_tolerates_small_lr_difference` passes at a 3-line difference.
- [ ] A throwing check degrades to one FAIL finding; other checks still run.
- [ ] Write-path traversal attempt is refused; tested.
- [ ] Determinism test passes.
- [ ] FIS is **never** checked and `QC_Pcs_Files.csv` is never read (both
      confirmed out of scope by Derek, 2026-10-28).
- [ ] Full test suite green.

---

## Phase 4 — The HTML report
**Complexity:** Moderate
**Goal:** One self-contained `.html` file a crew member can read and email, and a
machine-readable JSON alongside it.

### Dependencies
| Tool / Library | Version | Purpose |
|----------------|---------|---------|
| Jinja2 | 3.1.6 | Templating (from Phase 1) |

### Tasks
1. **`core/report/template.html.j2`** — single file, CSS inlined in a `<style>`
   block, no external fonts, scripts, or CDN links. It must render correctly from
   a local file with no network, and print to PDF sensibly.
2. **Report layout**, top to bottom:
   - Verdict banner: the word **PASS** / **NEEDS A LOOK** / **PROBLEM FOUND**,
     full width, colour-coded *and* spelled out (never colour alone — some crew
     members will print it in greyscale).
   - One line of context: project folder name, day, when it was checked.
   - One line of counts: sessions checked, warnings, problems.
   - **"What to do"** — the `what_to_do` lines, deduplicated, as the first thing
     after the banner. This is what the crew reads.
   - Findings, grouped by severity, problems first. Plain-English sentence,
     affected session, what to do.
   - **"Sessions collected"** — from the Daily: every session with status
     (Collected / Deleted / Collected short), section, length, collected length,
     and the crew's comment word for word; then "Explained by the crew"; then the
     footer metadata (software version, time in motion).
   - **"QC_Video check"** — one line: "QC_Video agreed with QCDATA on N of N" or
     the list of disagreements.
   - **Images summary** — counts per session, dropped images (if any), number of
     stops, and a link to the inventory CSV. Never the full per-image list.
   - A collapsed technical section: per-session table, per-check status,
     `message_technical`, derived steps, the suppressed partial-copy list,
     no-photo pulses, stops (photo number and duration), runs with no Daily row,
     the C8 message counts, PC-vs-GPS offset and drift, FrameID self-check
     results, unmatched DataLogger folders, and Qinertia projects per day.
3. **Autoescaping on** — construct the `Environment` with `autoescape=True`.
   Jinja2 does **not** autoescape by default. A filename containing `<script>`
   must render as visible text.
4. **`core/report/writer.py`** — write through the Phase 3 write-path guard to
   `<signoff>/_QCDATA/QCDATA_Report_<signoff folder>_<YYYYMMDD-HHMMSS>.html`,
   `findings_<signoff folder>_<timestamp>.json`, and
   `images_<signoff folder>_<timestamp>.csv` — one set per signoff folder, every
   day in it, with a per-day section and a one-line-per-day summary at the top (the full per-image inventory, columns as
   in the Instructions, with a comment header stating the time sources and their
   accuracy). **Only add files:** create each with exclusive-create mode `"x"`;
   on a name clash add `-2`, `-3`, …; never overwrite or touch anything else,
   including earlier reports, `QC_Pcs_Files.csv`, and `QC_Video.csv`.
5. **`cli/main.py`** — `qcdata check <drive_or_folder>` with `--days`, `--logs`,
   `--config`, `--json`, `--quiet`, `--out`, `--no-report` (no overwrite option); exit codes 0/1/2/3/4 exactly
   as specified. Follow `cli-api-standards.md`. `--json` writes machine-readable
   output to stdout and nothing else, so it can be piped.
6. Write the README with CLI usage, exit codes, and every config key documented.

### Done when:
- [ ] `uv run qcdata check SampleData\17thAnd16th` produces one report: the
      a section per day; the 20261017 section is PASS; the 20261016 section has
      no missing-data findings (its 44 `X` runs are explained); the exit code
      matches the overall verdict.
- [ ] The report opens in a browser from the local filesystem with no network and
      renders fully.
- [ ] XSS test: a fixture filename containing `<script>alert(1)</script>` renders
      as text; asserted in a test.
- [ ] Greyscale check: verdict is legible with colour removed (word present, not
      just a coloured bar).
- [ ] `--json` output parses and matches the findings JSON.
- [ ] All five exit codes reachable and tested.
- [ ] `test_only_adds_files` passes: after two runs, the only changes on the
      fixture root are new files under `_QCDATA\`; the first run's report is
      unchanged.
- [ ] `test_guard_refuses_overwrite` passes.
- [ ] Inventory CSV for the reference day opens in Excel with one row per image
      and no time taken from a file date.
- [ ] The "Sessions collected" section shows the 2026-10-17 Daily's 28 sessions
      with the crew comments unchanged.
- [ ] Full test suite green.

---

## Phase 5 — The GUI
**Complexity:** Moderate
**Goal:** The double-clickable app the crew actually uses. Thin presentation over
the Phase 3 engine — **no check logic in this layer.**

### Dependencies
| Tool / Library | Version | Purpose |
|----------------|---------|---------|
| PySide6 | 6.11.3 | Desktop GUI (from Phase 1) |

### Tasks
1. **Read `Specs/gui-coding-standards.md` again before writing a single widget.**
   Every rule in it is mandatory: dark mode, the 5-method `__init__`, named
   instance variables for every widget and layout, no logic in `_create_*`, named
   constants instead of magic numbers, slots named `_on_<widget>_<event>`.
2. **`gui/app.py`** — `main()` entry point, `QApplication`, main window, dark
   palette from `gui/styles.py`.
3. **`gui/main_window.py`** — `QTabWidget` with the three screens.
4. **`gui/screens/run_screen.py`** — folder picker (normally the drive root),
   optional log-folder picker (both remembered between runs), the **days list**
   (checkboxes, newest ticked by default, factory + populate + clear), Check button, progress bar, status label, verdict
   banner, Open Report button. Exactly the widget names
   given in the Instructions.
5. **`gui/worker.py`** — a `QThread` worker running the engine off the UI thread,
   emitting progress and completion signals. The window must never freeze; a day
   has ~12 000 files and may sit on a slow network path. Follow `ImageQC`'s
   precedent here.
6. **`gui/screens/results_screen.py`** — findings list and sessions table, both
   built with the **factory + populate + clear** pattern
   (`_create_finding_card_widget`, `_populate_findings_list`,
   `_clear_findings_list`, with `deleteLater()`), so a re-run rebuilds cleanly
   with no leaked widgets.
7. **`gui/screens/settings_screen.py`** — show the active thresholds, allow edits,
   write back to `config.yaml` through a validated setter, with Reset to Defaults.
8. **`gui/view_models.py`** — a UI-free layer translating `Finding` objects into
   display rows, so the presentation logic is testable without Qt.
9. **Remembered folders** (`gui/state.py`) — save the signoff and log folders to
   `qcdata_state.json` after each run; on start-up, restore them, trying each
   `data_drives` letter (`F:`, `G:`) if the remembered drive is gone, and say so
   in the status label. See Instructions, Run screen.
10. Verify `launch.bat` now opens the app on a clean machine with no `.venv`.

### Done when:
- [ ] `launch.bat` double-clicked on a machine with no `.venv` sets up and opens
      the app.
- [ ] Close and reopen: both folders are filled in. Rename the drive's path from
      `F:` to `G:` (or simulate it in a test): the folder is still found, and the
      status label says where.
- [ ] A full check on the reference day runs without the window freezing, with
      live progress.
- [ ] Verdict banner shows the right state for all three verdicts (forced via
      fixtures).
- [ ] Re-running twice in one session leaves no duplicated or leaked widgets
      (asserted on layout child count).
- [ ] Settings edits persist to `config.yaml` and take effect on the next run.
- [ ] Offscreen GUI smoke test passes (`QT_QPA_PLATFORM=offscreen`).
- [ ] Every item on the `gui-coding-standards.md` pre-submit checklist verified
      and reported, line by line.
- [ ] **Human review step** — Derek reviews the layout before proceeding.
- [ ] Full test suite green.

---

## Phase 6 — MS SQL database check (C13) — ⛔ BLOCKED
**Complexity:** Moderate
**Goal:** Reconcile what is on disk against the live MS SQL database.

> **Do not start this phase until Derek has supplied the database details.** The
> Instructions list them as reference gap 1: server, database, schema, table and
> column names, the expected row grain, and read-only credentials. None are known
> at spec time, and Derek has said to hold it until the project is on a machine
> with access to the live server.
>
> **Phase 6 begins with an interview, not with code.** Ask, confirm, then build.
> Guessing a schema here produces a check that silently passes.

### Dependencies
| Tool / Library | Version | Purpose |
|----------------|---------|---------|
| pyodbc | 5.3.0 | MS SQL connectivity — added in this phase, not before |
| Microsoft ODBC Driver for SQL Server | 18 or as installed | Required by pyodbc; confirm what is on the machine |

### Tasks
1. **Interview first.** Confirm every item in reference gap 1. Write the answers
   into `CONTEXT.md` before writing code.
2. `core/db/connection.py` — connection from `.env` parts, never concatenated
   from user input. Read-only account. Connection timeout set. On any failure,
   degrade to a "database not checked" WARN; **never** hang and never crash the
   run. The file-based checks must still produce a report with no database.
3. `core/db/queries.py` — **parameterized queries only.** No f-string SQL, no
   string concatenation, no dynamic table names from config without an allow-list.
4. `core/checks/c13_database.py` — disk-not-in-DB → FAIL; DB-not-on-disk → WARN.
   Aggregate like C8; do not emit one finding per missing row.
5. Add a `--no-db` CLI flag and a Settings toggle so the DB check can be skipped
   when off the collection network.
6. Tests against a mocked connection plus, if feasible, a local SQL Server
   Express or a container. No test may require the live production database.
7. Never log the connection string or password; scrub them from error text. Test
   that an auth failure's message contains no credential.

### Done when:
- [ ] Database details confirmed in writing and recorded in `CONTEXT.md`.
- [ ] C13 finds a session present on disk and absent from the database.
- [ ] With the database unreachable, the run completes and reports "database not
      checked" as a WARN, with every file check still performed.
- [ ] No SQL built by string concatenation anywhere; verified by review and grep.
- [ ] Credentials absent from logs and from all error messages; tested.
- [ ] **Strongest-tier implementation plus a human security review** — this phase
      touches credentials and external calls.
- [ ] Full test suite green.

---

## Phase 7 — Security hardening and packaging
**Complexity:** Moderate
**Goal:** Prove the safety properties, then make it installable.

### Dependencies
| Tool / Library | Version | Purpose |
|----------------|---------|---------|
| pip-audit | latest | Dependency vulnerability audit |
| PyInstaller | 6.22.3 | One-folder `QCDATA.exe` build |

### Tasks
1. Re-read `Specs/security-standards.md` and audit the whole codebase against it.
2. **Prove add-only.** Snapshot every file on a full drive-root fixture (path,
   size, modified time, hash) before and after two runs; assert the only
   differences are new files under `_QCDATA\`. Also run once against a
   read-only copy: the app must write nothing there and say so.
3. **Prove bounded reads.** No log file is ever read whole; assert streaming on a
   synthetic 20 MB log. Confirm memory stays flat on a full day.
4. Confirm finding caps, per-check exception isolation, and the write-path guard
   all hold under fixtures designed to break them.
5. Run `pip-audit`; resolve every high/critical finding before the gate.
6. **Build the standalone** (decided: one-folder, no installer). A checked-in
   `QCDATA.spec` for PyInstaller `--onedir --windowed`, excluding unused Qt
   modules; `config.yaml` copied beside the exe; a `build.bat` that runs the
   build and zips it to `dist\QCDATA_<version>.zip`. Test on a clean Windows
   machine with no Python: unzip, double-click, run a full check. Note the
   SmartScreen first-run prompt in the README.
7. Write `..\..\095_WhatMyAppDoes\QCDATA.md` — house convention, one file per app.
   Derek prefers these **written from the actual source code**, not from the
   README. Read the code and describe what it does.
8. Finalise `CONTEXT.md`: current status, what is authoritative, remaining gaps.

### Done when:
- [ ] Add-only proven: nothing existing changed after two runs; read-only drive
      handled without writing.
- [ ] `pip-audit` clean (or every finding documented and accepted).
- [ ] Streaming and memory bounds verified on a synthetic 20 MB log.
- [ ] `QCDATA_<version>.zip` built by `build.bat`; on a clean machine with no
      Python it unzips, starts, runs a full check, and writes its report; size
      recorded.
- [ ] Settings edits and remembered folders persist beside the exe (or in
      `%APPDATA%\QCDATA\` when the folder is read-only).
- [ ] `QCDATA.md` written from the source and placed in `095_WhatMyAppDoes`.
- [ ] `CONTEXT.md` current.
- [ ] Full test suite green.

---

## Phase 8 — Tuning against the full dataset and signoff
**Complexity:** Moderate
**Goal:** Replace provisional thresholds with ones earned from real data, and
confirm the report is actually readable by its actual reader.

> The thresholds in the Instructions came mostly from 2026-10-17 (the tail check
> from every folder in `100_Signoff`). They are starting points, not truth. Derek is supplying more
> collection days.

### Dependencies
No new packages.

### Tasks
1. Run the app across every available collection day. Record, per check, how
   often it fires and on what.
2. **Hunt false positives.** Any check firing on data Derek confirms is good is a
   bug in the check or the threshold, not a finding. Re-tune `config.yaml`
   defaults and document each change with the evidence behind it.
   Specifically re-examine: the C6 end tolerance (`warn_m` 3.0 / `fail_m` 8.0),
   the C10 L/R tolerance (25 rows / 1%), the C8 code list, and the C5 step
   derivation — if C5 fires often, the step derivation is wrong before the data is.
3. **Mid-run hole test.** No real session has a mid-run hole, so neither C5 nor
   QC_Video has been tested on one. Make a *copy* of one session (never edit the
   original), delete a middle frame, run QCDATA, and — if Derek can — have the
   collection software regenerate `QC_Video.csv` on the same copy. That one test
   answers whether QC_Video catches mid-run holes.
4. **QC_Video suspicion.** Ask Derek which day or session made him doubt
   QC_Video, and run C14 on it. If he has none, report that across the whole
   corpus QC_Video was never found wrong, only limited in what it checks.
5. **Read-aloud test.** Have someone who has not seen the app read a WARN report
   and say what they would do. If they cannot, the wording failed — rewrite it.
   This is a real acceptance criterion, not a nicety: the whole app exists to be
   understood by a non-technical reader at the end of a long day.
6. Confirm with Derek that the runs with no Daily row on the reference day are
   false starts, and that the technical-section wording fits.
7. Final full-suite run and a short summary of every threshold changed and why.

### Done when:
- [ ] Every check exercised against the full dataset; firing rates reported.
- [ ] No known false positives remain, or each is documented and justified.
- [ ] Thresholds finalised in `config.yaml`, each change evidenced.
- [ ] Mid-run hole test done; C5 catches it; QC_Video's behaviour on it recorded.
- [ ] C14 run on Derek's suspect case (or "none supplied" recorded).
- [ ] `laser_short_pulses` re-checked against the fuller dataset.
- [ ] A non-technical reader correctly states what to do from a WARN report.
- [ ] Full test suite green; `pip-audit` clean.
- [ ] Derek signs off.

---

## Agent routing per phase (capability-based, with named defaults)

Route by tier; the strongest tier is the default and supervisor. Pair the tier
with the current default model so this survives model renames.

*Model names as of 2026-10-28. The spec-builder skill's own table was last
verified in July 2026 and had gone stale (it listed Claude Sonnet 5 and Claude
Haiku 4.5); the table below is the corrected current lineup. Confirm the names if
this spec is much older than its date.*

| Tier | Default model | Model string |
|------|---------------|--------------|
| Strongest | Claude Opus 5.5 (or Claude Opus 5) | `claude-opus-5-5` / `claude-opus-5` |
| Mid | Claude Sonnet 5.5 | `claude-sonnet-5-5` |
| Cheapest | Claude Haiku 5.5 | `claude-haiku-5-5` |

| Phase | Recommended tier (current default) |
|-------|-----------------------------------|
| 1 — Environment Setup | mid (Sonnet 5.5) |
| 2 — Parsers and data model | mid (Sonnet 5.5); **strongest** for the image-step derivation and the `SessionId` normalization — everything joins on these |
| 3 — Check engine | **strongest** (Opus 5.5) — this is the architecture, the partial-copy guard, and the verdict model |
| 4 — HTML report | mid (Sonnet 5.5); **strongest** for the autoescaping/XSS work |
| 5 — GUI | mid (Sonnet 5.5) + **human review step** |
| 6 — MS SQL check | **strongest** (Opus 5.5) + **human security review** — credentials and external calls |
| 7 — Security hardening and packaging | **strongest** (Opus 5.5) + human review |
| 8 — Tuning and signoff | **strongest** (Opus 5.5) — judgment about false positives and crew-facing wording |
| Trivial mechanical edits (any phase) | cheapest (Haiku 5.5) |
| **Phase-gate decisions (every phase)** | **strongest — never delegated** |

When in doubt, use the strongest tier. Escalate anything questionable.

---

## Total estimate

| Phase | Complexity | Blocked? |
|-------|------------|----------|
| 1 — Environment Setup | Simple | No |
| 2 — Parsers and data model | Moderate | No |
| 3 — Check engine | **Complex** | No |
| 4 — HTML report | Moderate | No |
| 5 — GUI | Moderate | No |
| 6 — MS SQL check | Moderate | **Yes — needs DB details** |
| 7 — Security and packaging | Moderate | No |
| 8 — Tuning and signoff | Moderate | Partly — needs the fuller dataset |

**Phases 1–5 deliver a working, shippable app** that checks files, filenames, and
logs and reports in plain English. Phase 6 adds the database. Phases 7–8 harden
and tune it. Build 1–5 first and get it in front of the crew; the database check
is additive, not foundational.

---
