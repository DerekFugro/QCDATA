---
# Instructions for QCDATA

> This spec is self-contained. The coding agent may have no prior context — every
> rule here is explicit. Default to the strongest model tier (see the routing
> table below) unless a task is explicitly routed lower.
>
> **Spec written:** 2026-10-28. Stack versions verified against PyPI on that date.

## ⭐ Project name:
**QCDATA** — Sidewalk Collection Data Completeness QC.

Python package name: `qcdata`. Project root:
`F:\Sidewalk\002_App\SidewalkProfilier\001_DataChecking\QCDATA`

This is a **sidewalk** QC project, part of the SidewalkProfilier app suite. It is
*not* an ARAN application. The ARAN name appears only inside data filenames
produced by the collection vehicle's software (`ARAN01_*`); do not infer from
those filenames that this tool belongs to an ARAN product line, and do not name
anything in the codebase "ARAN".

## ⭐ Purpose:
Confirm that a day's sidewalk collection is **complete** before it is signed off.
The app reads a signoff folder — the day's export files, the collection logs, and
the image/profile payload — cross-checks them against each other, and produces a
single plain-language HTML report telling a non-technical crew member whether the
data is all there.

## ⭐ Problem it solves:
Today, completeness is confirmed by eye. A collection day produces tens of
sessions and tens of thousands of files across three separate payload folders,
and the authoritative list of what was collected lives in a different file from
the data itself. Nothing cross-checks them. Consequences:

- A copy can **miss whole pieces**. One copy arrived with no SBG DataLogger
  folders for a day and without the previous day's Qinertia projects. Nothing
  checks each part separately today.
- A session can be **exported but have no payload** — the record says a section
  was collected, but the image and profile folders are missing.
- Image frames can be **dropped mid-run** when the vehicle speeds. The collection
  software warns about this at the time, but nothing afterwards checks whether
  frames were actually lost. Verified in sample data: the warning fired on
  2026-10-17 session `165541`, and no frames were in fact lost — so the warning
  alone is not evidence of loss, and loss must be measured directly.
- The SBG unit logs every **camera pulse** it sends (`eventOutA.txt`). Comparing
  pulses with photos is the only *direct* measure of dropped photos — ACS doesn't
  log pulses or missed frames (confirmed by Derek). Nothing does it today.
- The collection software writes `QC_Video.csv`, which Derek suspects is not
  working correctly. It was checked against an independent re-derivation on
  2026-10-28 (see "QC_Video.csv" below): it matched on every case that could be
  checked, but it only detects one kind of loss. QCDATA re-derives the same result
  independently and reports any disagreement, so QC_Video is verified on every run
  rather than trusted.
- The `Daily_*.csv` is the **crew's own record** of each session — collected,
  deleted, or collected short, with a reason. Any check that ignores it will
  flag problems the crew already explained.
- There is a **live MS SQL database** that should hold a record of everything
  collected. Nothing reconciles the files on disk against it.

Discovering any of these after the crew has left the site means re-collecting a
day. The cost of a missed check is a return trip.

## ⭐ MVP definition:
A double-clickable Windows desktop app where a crew member browses to a signoff
folder, presses one button, and gets:

1. A **PASS / WARN / FAIL** verdict on screen, large and unmistakable.
2. A **single self-contained HTML report** written next to the data, listing every
   finding in plain English with what to do about it, plus a **"Sessions
   collected"** section read from the Daily (see below).
3. A **per-photo CSV** — one row per photo with its run, view, photo number,
   pulse, and the time it was taken: PC time (what the van PC would have stamped
   on the file) and GPS time. The HTML report shows only a summary (stops, drops);
   the full list is for audit and opens in Excel.

MVP covers the file, filename, log, trigger, and QC_Video checks (C1–C11 and
C14–C17 below). The database check (C13) is specified here but **deliberately
deferred to Phase 6** — it cannot be built or tested until the project is on a
machine with access to the live MS SQL server. Build the data model so C13 drops
in without rework.

## ⭐ Success criteria:
1. On the reference day (`SampleData\17thAnd16th\20261017`), that day's section
   of the report is **PASS** — no crew-section warnings or failures. (The `17thAnd16th` folder's other day, 20261016, is covered by criterion 2.) Under "Explained by the crew": the three runs marked
   `X` in the Daily (`142650`, `160558`, `161445`, "ACS NAN error"), including
   `160558`'s empty laser files. Zero dropped photos; no missing or gapped laser
   files. In the technical section only:
   - runs on disk with no Daily row: `141947`, `154142` (false starts — not part
     of the day);
   - one pulse in `154422` less than 0.13 s after the previous one, so no photo;
   - the stops (C16);
   - the PC-vs-GPS offset, 3651.6 s with the PC ahead, and its drift;
   - GPS mode `NoSolution` on every Daily row;
   - `154208`: both lasers started one pulse (≈0.75 m) after the cameras — within
     the normal two.
2. On `20261016` (48 exported runs, 4 with photos), the app reports **no
   missing-data findings**: the Daily marks the 44 runs without photos as `X`
   (deleted by the crew), and the 4 `C` runs are exactly the 4 with photos
   (found in Phase 2). The 44 are listed under "Explained by the crew". The
   **partial-copy guard** (below) is still required and still the most important
   behaviour — a report that cries wolf 44 times will be ignored, and then a real
   failure will be ignored with it — but it is now tested on a synthetic day
   whose Daily marks the runs `C`.
3. A crew member who has never seen the app can get a verdict in under 60 seconds
   without being told what a "UniqueRun" is.
4. Every finding names the affected session and says what to do next.
5. Re-running on unchanged data produces an identical report (deterministic).
6. **The app only ever adds new files.** It never changes, renames, moves, or
   deletes any existing file or folder on the data drive — collected data, logs,
   or its own earlier reports (confirmed by Derek: "no data can change, we can
   only add files").
7. On 2026-10-09 (`20261009_New_Reverse_run` and `20261009_NeW_Reverse_Run_Tape`),
   C14 agrees with `QC_Video.csv` on **all 28** session-views where images exist —
   same last image, same session end, same missing count — and reports zero
   disagreements.
8. On every other day available, where `QC_Video.csv` is empty, C14 also finds
   nothing to report.
9. On the multi-day reference `Zipfiles\Batch1` (six days), one run produces
   **one** report with a section per day and a one-line-per-day summary. Oct 15
   gets a WARN — "export log not found; choose the folder that holds it" — and its
   runs are still checked from the Daily. Oct 16's two exports are combined. The
   overall verdict is the worst day's.

## ⭐ Explicit non-goals / out of scope:
- **Image content quality.** Exposure, blur, and obstruction are `ImageQC`'s job
  (sibling app at `..\ImageQC`). QCDATA answers "is the data there?", not "is the
  data good?". Note the deliberate overlap: ImageQC checks frame gaps *within one
  camera session*; QCDATA checks them *across a whole day* and against the export
  record. Do not merge the two apps.
- Profile/laser processing, IRI or rut computation, orthorectification.
- Repairing, re-exporting, moving, or re-collecting data. QCDATA reads, and only
  ever adds its own new report files.
- Evaluating whether the *right* sections were collected against a work order.
  `Sections_Not_Collected_List.csv` is read and reported as a count only; deciding
  whether an uncollected section matters is a human judgment.
- Settings correctness. That is `ProjectCompare`'s job (`F:\AranApps\ProjectCompare`).
- Any network service, web UI, multi-user access, or cloud upload.
- **Sample photos outside the root `Images\` folder** (the Morning / Mid-Day /
  Evening folders in each day folder, and their `ReadMe.txt`) — they don't matter
  (confirmed by Derek, 2026-10-28). Never read them.
- **The FIS camera.** It is not used on this rig (confirmed by Derek, 2026-10-28).
  Do not check `FIS` folders, and never report their absence or emptiness.
- **`QC_Pcs_Files.csv`.** Obsolete — PCS data is now SBG data (confirmed by Derek,
  2026-10-28). Ignore the file entirely; do not read, check, or report it.
- **Fixing time sync on the vehicle.** QCDATA *reports* the PC-clock vs GPS-time
  offset (C17); diagnosing it is a hardware task.

## ⭐ Primary user / persona:
**A non-technical field crew member**, at the end of a collection day, possibly in
a vehicle, possibly tired, who needs to know whether they can leave the site.

Consequences that are requirements, not suggestions:
- No jargon in the UI or report. Not "UniqueRun" — say "collection session". Not
  "distance stamp mismatch" — say "the images stop short of where the run was
  recorded to end".
- No command line, no Python, no config editing needed for normal use.
- Every finding must answer "so what do I do?".
- The app must work with no network and no database available, degrading to
  "database not checked" rather than failing.

Secondary user: Derek (the author), who will also run it from a CLI while
developing and may inspect the config file.

## ⭐ Top user stories:
1. As a crew member, I browse to today's signoff folder, click **Check**, and see
   PASS, WARN, or FAIL within a minute.
2. As a crew member, when something is wrong I see which session, in plain words,
   and what to do about it.
3. As a crew member, I can send the report to the office as one file attachment.
4. As a crew member, when I've only copied part of a day I get told that once,
   not once per session.
5. As Derek, I can run `qcdata check <folder>` from a terminal and get a non-zero
   exit code when the verdict is FAIL, so it can be scripted.
6. As Derek, I can change what counts as a warning versus a failure in
   `config.yaml` without touching Python.
7. As Derek (Phase 6, on the collection network), I can have the app confirm that
   every session on disk also has rows in the MS SQL database.
8. As Derek, I can open a CSV listing every photo with the time it was taken —
   the PC time the van would have stamped on the file, and GPS time — to audit a
   day or line photos up with other sensor data.
9. As a crew member, I can see a list of the sessions the Daily says were
   collected, deleted, or collected short, with the crew's own reasons.
10. As Derek, I can see whether `QC_Video.csv` agreed with QCDATA's own analysis,
    so I know whether QC_Video can be trusted.
11. As Derek, I can see where the vehicle stopped mid-run, and whether the PC
    clock and GPS time drifted apart, in a technical section the crew does not
    have to read.

## ⭐ App type:
**GUI desktop** (Windows, PySide6) with a secondary CLI adapter over the same
engine. Three layers, in dependency order: `core` (UI-free engine) ← `cli` ←
`gui`. The engine must be fully testable with no Qt import.

## ⭐ Platform standards to follow:
Read these **before writing any code**, and follow them exactly:

- `Specs/gui-coding-standards.md` — **mandatory for all GUI code.** Dark mode;
  the 5-method `__init__` pattern (`_create_widgets`, `_create_layouts`,
  `_connect_signals`, `_apply_styles`, `_load_initial_state`); every widget and
  layout gets a named instance variable; no business logic in any `_create_*`
  method; dynamic widgets use the factory + populate + clear pattern with
  `deleteLater()`; slots named `_on_<widget>_<event>`; no magic numbers.
- `Specs/cli-api-standards.md` — for the CLI adapter.
- `Specs/security-standards.md` — cross-cutting; applies because the app reads
  untrusted file paths and filenames, and in Phase 6 connects to a database.

**GUI layout approach:** hand-written PySide6 in Python. **No `.ui` files** and no
Qt Designer — consistent with `ImageQC` and `ReverseRunProcessor`.

**Dynamic widgets needing the factory pattern:** the findings list (one card per
finding) and the per-session results table rows. Both are built at runtime from
engine results and must be rebuilt cleanly on re-run.

## ⭐ Key screens / endpoints / commands:

### GUI — three screens, tabbed
**1. Run** (opens here)
- `self.folder_path_input` (read-only) + `self.browse_button` → folder picker.
- `self.log_folder_input` (read-only) + `self.log_folder_button` — optional
  **Log folder**, for when export logs or ACS logs were copied somewhere other
  than the day folders.
- `self.days_list` — the day folders found, newest first, each with a checkbox
  and its date; **the newest day is ticked by default**, with Select all / None.
  A collection drive can hold many days, so checking only the new one keeps a
  run quick and the report short. Built with the factory + populate + clear
  pattern. The report covers the ticked days.
- **Both folders are remembered between runs** (confirmed by Derek), in the
  state file (see "Where the app writes"). The signoff folder will normally be
  the drive root itself. Signoff data lives on **`F:\` or
  `G:\`** — usually removable drives whose letter can change. On start-up, if a
  remembered folder no longer exists, try the same path on each drive letter in
  `data_drives` (config, default `["F:", "G:"]`) and use the first that exists,
  telling the user in the status label ("Found your last folder on G: instead of
  F:"). If none exists, leave the field empty and open the folder picker at the
  first `data_drives` letter that exists.
- `self.check_button` — large, primary. Disabled until a valid folder is chosen.
- `self.progress_bar` + `self.status_label` — live progress; the engine runs on a
  `QThread` worker so the window never freezes.
- `self.verdict_banner` — after the run: full-width, PASS green / WARN amber /
  FAIL red, with the verdict word spelled out, not just coloured.
- `self.open_report_button` — opens the HTML report in the default browser.

**2. Results**
- `self.summary_label` — e.g. "28 sessions checked, 2 warnings, 0 failures".
- `self.findings_list` — one card per finding: severity chip, plain-English
  sentence, affected session, and a "what to do" line.
- `self.collected_table` — **"Sessions collected"**, read from the Daily: one row
  per session with status (Collected / Deleted / Collected short), section,
  length, and the crew's comment, in the crew's own words. Shown to the crew.
- `self.sessions_table` — one row per session with per-check status, trigger
  count, image counts, longest stop, and clock offset. Collapsed / secondary; the
  crew does not need it, Derek does.
- `self.open_inventory_button` — opens the per-image CSV in the default program.

**3. Settings**
- Shows the active thresholds read from `config.yaml`, editable, with a Reset to
  Defaults button. Changes are written back to `config.yaml`.

### CLI
```
qcdata check <drive_or_folder> [--days 20261017,20261018 | --days all]
                               [--logs PATH] [--config PATH] [--json] [--quiet]
                               [--out PATH] [--no-report]
                               [--no-db]         (Phase 6: skip the database check)
qcdata version
```
`<drive_or_folder>` is a drive root (`F:\`, `G:\`) or a copied folder with the same
shape. `--days` defaults to the newest day found. `--out` puts the report files
in another folder instead of `<root>\_QCDATA\`; it still only adds files. There is
no option to overwrite anything.

Exit codes (document these in the README):
`0` PASS · `1` WARN · `2` FAIL · `3` bad usage / folder not found ·
`4` folder found but unreadable or not a recognizable signoff folder.

Rationale for WARN being non-zero but distinct from FAIL: it lets a future
script treat warnings as advisory without conflating them with real loss.

## ⭐ Roles / permissions:
None. Single-user desktop app, no authentication, no multi-user state.

## ⭐ Data to store + key rules:

### What the app reads

A **signoff folder** (e.g. `F:\001_BuggyData\001_RawData\100_Signoff\17thAnd16th`)
contains one or more **day folders** named `YYYYMMDD`, plus three payload folders
shared across days:

```
<signoff folder>/
  20261017/                               <- day folder
    ARAN01_Export_<YYYYMMDDHHMMSS>_log.csv   <- AUTHORITY on what was exported
    ARAN01_StatusMessages_20261017.csv       <- every session STARTED, + warnings
    ARAN01_Settings_20261017.xml             <- settings snapshot
    Daily_ARAN01_20261017.csv                <- one row per exported section
    Collected_Length_By_Func_Class.csv
    Sections_Collected_List.csv
    Sections_Not_Collected_List.csv
    QC_Pcs_Files.csv                         <- OBSOLETE (PCS is now SBG) — ignore
    QC_Video.csv                             <- collection software's tail check;
                                                QCDATA verifies it (C14), never writes it
    Morning/ | Mid-Day/ | Evening/           <- sample photos + ReadMe.txt receipts:
                                                IGNORED (only the root Images\ matters)
      ROW/ Rear/ FIS/                        <- a few sample JPEGs; FIS unused — ignore
    Logs/ARAN01-SERVER/*.log[.N]             <- rotated service logs, up to ~20 MB each
  Images/<session>/{ROW,Rear}/*.jpg          <- payload, keyed by session
  GoCatorData/<session>/<stamp>{L,R}.csv     <- payload, keyed by session
  SBGData/
    <YYMMDD>/<session> DataLogger/           <- raw SBG logs per session (note the
                                                space + "DataLogger" suffix)
      eventOutA.txt                          <- camera pulses (the one QCDATA counts)
      eventOutB.txt  eventInA.txt            <- same pulses; roles unconfirmed
      utcTime.txt                            <- device clock -> GPS UTC, 1 Hz
      DmiStationEx <session>.csv             <- not needed by QCDATA
      (nav, euler, gnss1*, imuShort, ...)    <- not used by QCDATA
    <YYMMDD>/<session>/                      <- older sessions: raw .000/.001 files
    <session>_0001/                          <- post-processed project (Qinertia)
```

### The standard layout — the drive root (confirmed by Derek)
On the collection drive the data sits at the **drive root**, which can be `F:\` or
`G:\` (confirmed by Derek, 2026-10-28):

```
F:\GoCatorData\      (lasers)
F:\Images\           (photos)
F:\SBGData\          (SBG)
F:\<YYYYMMDD>\       (one day folder per day — the Daily files and logs)
```

This is exactly the shape of `F:\001_BuggyData\001_RawData\100_Signoff\17thAnd16th`
(confirmed by Derek: "files are like this") — `20261016\`, `20261017\`,
`GoCatorData\`, `Images\`, `SBGData\`, nothing else. `Zipfiles\Batch1` has the
same shape plus root export folders. **QCDATA accepts either a drive root or a folder with that shape**, and
treats both the same. At a drive root, ignore everything that isn't a day folder,
a payload folder, or a root export folder (`$RECYCLE.BIN`, `System Volume
Information`, unrelated folders).

**Payload folder names are settings, not code** — `folders:` in `config.yaml`,
matched ignoring case. Defaults: `Images`, `GoCatorData`, `SBGData` (confirmed —
the drive matches `17thAnd16th`).

The full shape, using `Zipfiles\Batch1` (six days) as the worked example:

```
<signoff folder>/
  20261009/ 20261010/ 20261014/ ...     <- one day folder per day (YYYYMMDD)
  Images/<session>/{ROW,Rear}/          <- shared across ALL days
  GoCatorData/<session>/                <- shared across ALL days
    ReviewData_<session>.csv            <- not a session folder — ignore
  SBGData/<YYMMDD>/<session> DataLogger/  <- one YYMMDD folder per day
  SBGData/<session>_0001/               <- post-processed projects
  ExportBakFiles/ARAN01_Export_<stamp>_log.csv  (+ .bak — ignore the .bak)
  ExportLogs/ARAN01_Export_<stamp>_export_log.csv   <- export PROCESS log, not a run list
  ExportDataFiles/*.mdf, *.ldf          <- not checked — ignore
```

Rules that follow from it:

- **One run checks every day folder** in the signoff folder. **The runs to check
  come from each day's Daily** (see below), not from the payload folders. Payload is shared,
  so payload sessions are assigned to days by the **date prefix of the session
  id**, never by folder.
- **Run lists can be in the day folder or root `ExportBakFiles\`** (or the extra
  log folder), and the same export often appears in more than one. In `Batch1`,
  four of six days had no run list in the day folder. **Tell a run list by its
  header** (`UniqueRun,SectionName,...`), never by its name: the
  `ExportLogs\*_export_log.csv` files are export *process* logs
  (`IDExportLogDetail,ExportDBName,ExportStepName,...`) and list no runs (found in
  Phase 2). Collect every run list, **de-duplicate**, and assign rows to days by
  run id. The stamp in an export's filename is the *export* time, not the
  collection day.
- **A day can be exported more than once** (Oct 16 in `Batch1`: a 09:39 export of
  the first 2 runs, then all 48 again at 18:07 — 48 runs in total). Union them.
- **A day with a Daily but no export log found is a WARN for that day:** "The
  export log for this day wasn't found. If it was copied somewhere else, choose
  that folder as the log folder and check again." Logs are copied separately and
  can end up elsewhere (confirmed by Derek) — see "Logs". In `Batch1`, Oct 15 is
  this case (37 Daily rows, no export log in the folder). The run list comes from
  the Daily, so the payload checks still run.
- **Payload sessions with no day folder** (images for a date that has no
  `YYYYMMDD` folder) are a WARN: "Images found for a day with no day folder."
- Ignore: `ExportBakFiles\*.bak`, `GoCatorData\ReviewData_*.csv`, PNG
  screenshots in day folders, and `QC_Pcs_Files.csv`.
- `ExportDataFiles\` (`.mdf`, `.ldf`) — **not checked** (confirmed by Derek).
- Image extensions appear as both `.jpg` and `.JPG`. Match case-insensitively.
- **Anything not in this shape** (a folder with no `YYYYMMDD` day folders, or
  with day folders but none of `Images\` / `GoCatorData\` / `SBGData\`) gets a
  clear "This doesn't look like a signoff folder" message naming what is missing
  — not a crash, and not a guess. Some older folders in `100_Signoff` are nested
  differently (`20261020 2\20261020\20261020\`); supporting those is **out of
  scope**.

### Reporting with many days
- **One HTML report per signoff folder**, with a section per day, and one overall
  verdict = the worst day's verdict. The crew picks one folder and gets one
  answer.
- At the top, a **one-line-per-day summary**: date, sessions, verdict.
- **One per-image inventory CSV per signoff folder**, with a `day` column.
- File names: `QCDATA_Report_<signoff folder name>_<YYYYMMDD-HHMMSS>.html`,
  `findings_<...>.json`, `images_<...>.csv`.

### The join key
Every cross-check hangs on the **session id** (the collection software calls it
`UniqueRun`): `YYYYMMDD.HHMMSS`, e.g. `20261017.153218`. It appears:

- in the export log and `Daily_*.csv` as `[20261017.153218]` — **bracketed**;
- in `StatusMessages` as `[20261017.153218]` in the `FileName` column;
- as a **folder name, unbracketed**, under `Images/` and `GoCatorData/`;

**Rule:** strip brackets on parse and normalize to the bare `YYYYMMDD.HHMMSS`
form everywhere internally. Match with `^\[?(\d{8}\.\d{6})\]?`.

### Critical filename rule — image names are photo counts, not positions
Photos are named **photo count × 750 mm**, zero-padded to 12 digits:
`000000075000.jpg` is photo number 100. Confirmed by Derek, and by the camera
log, whose `FrameID: 100` line names `...\000000075000.jpg`. **The name says
nothing about where the photo was really taken** — the photo's pulse does (see
"Camera pulses").

- Photo number = filename ÷ step. The first photo of every run is `000000000750`.
- The step **must not be hard-coded.** Derive it per run as the most common gap
  between sorted filenames. `config.yaml` holds the expected step as a cross-check
  only; a different derived step is itself a WARN.
- A missing name in the sequence (C5) is a missing *photo* — never written, or
  deleted — not a gap in the road.
- C6 and QC_Video compare photo count × 0.75 m with the run's recorded end. That
  works because pulses are spaced by distance, but it is an approximation (±2 m
  seen on good runs), not a position.
- Do **not** compare the first photo with `BeginDistanceStamp`.

### The Daily is the list of runs — read it first
`<day>/Daily_ARAN01_<day>.csv`, written by the crew, is the **authority on which
runs belong to the day** (confirmed by Derek).

- **The Daily has an `Averages:` summary row** before the footer (first cell
  empty) — metadata, not a run. A `[0]` row's status is `U`; that is not an
  "unknown status" finding. A run can be `C` with a comment starting `Delete File`
  (e.g. `20261016.172652`) — the status decides; show the comment.
- **`Status`:** `C` = collected → check. `V` = verification → check exactly like
  `C`. `X` = deleted by the crew → don't check; list under "Explained by the
  crew" with the crew's comment. Any other value → report as unknown; don't guess.
- **A run with no Daily row is not part of the day.** Photos, laser files, or log
  lines for such runs (false starts — `141947` and `154142` on 2026-10-17) are
  listed in the technical section only and never raise the verdict.
- **A row can be valid with blank `LatBeg` / `LongBeg`.** Missing positions are
  not a finding.
- **`Comments`** is free text with recurring prefixes: `Delete File - <reason>`,
  `Section Collected Short - <reason>`, `Other - <reason>`. Classify by prefix;
  always show the full text unchanged.
- **The footer is metadata, not runs.** Rows whose `FILENAME` is not a run id —
  `ACS Version 2.6.5.774`, `Daily Report Version 1.0.0.0`, `Time in motion - 2h 0m
  24s` — become report metadata. Row 2 is a blank spacer. A `[0]` row (a section
  with no run, e.g. "sidewalk does not exist") is listed, never joined.
- Read every column by header name, never by position.

**The explained-findings rule.** Before a check emits a WARN or FAIL for a run,
look the run up in the Daily. A run whose comment contains `Section Collected Short`
(often after an `Other - ...` note)
has its short-tail finding (C6) moved to "Explained by the crew" at PASS.
Explained findings stay visible and never raise the verdict.

On 2026-10-17 the Daily has 25 `C` and 3 `X` rows. The three `X` runs are exactly
the three with a zero end distance in the export log; one of them (`160558`) also
has empty laser files.

### Camera pulses — the direct measure of dropped photos
Source: `SBGData/<yymmdd>/<run> DataLogger/eventOutA.txt` — one line per pulse
sent to the cameras. ACS does not log pulses, missed frames, or trigger settings;
they show up only here and in the photos (confirmed by Derek).

**Parsing (verified on 2026-10-17):**
- Tab-separated; two header lines (`timestamp status ...`, then units); one row
  per pulse; CRLF line endings.
- **Timestamps are right-aligned** — fewer digits means leading spaces. Parse with
  `line.split()` and accept any row whose first token is an integer. A
  starts-with-a-digit test silently drops rows; this bug was hit during spec
  research and needs a regression test.
- **The timestamp is a 32-bit microsecond counter. It rolls over every
  4 294.967 296 s (about 71.6 minutes).** Unwrap it: whenever a value drops by
  more than half the range, add 2³² to it and to every later value in that file.
  Do the same in `utcTime.txt`. On 2026-10-17, run `170358` rolled over mid-run;
  without unwrapping, its photo times came out 71.6 min wrong. (An earlier draft
  of this spec read the counter dropping between runs as "SBG restarts". They were
  rollovers.)
- **Matching DataLogger folders to runs:** the folder name can be 1 s off the run
  (`154209` ↔ `154208`, `154928` ↔ `154927`). Match within ±2 s. DataLogger
  folders with no run (`151624`, `163727` on 2026-10-17) go in the technical
  section.

**Expected photo count (confirmed by Derek; checked against the data):**
- **Photos = pulses + 1.** Photo 1 is a start-up frame with no pulse. Photo `k`
  (k ≥ 2) belongs to pulse `k − 1`.
- **A pulse less than `min_pulse_gap_s` (0.13 s) after the previous one gets no
  photo.** Drop those pulses before counting. Normal gaps go down to 0.145 s, at
  about 19 km/h. This happened once on 2026-10-17, in `154422`.
- **One or two photos short at the end is normal** — the cameras stop while still
  moving. PASS; noted in the technical section.
- **Short at the start** means the cameras weren't ready. WARN.
- **More than two short** → WARN (C6 also catches a large missing tail).
- **More photos than pulses + 1 is a real problem.** FAIL.
- **Rear and ROW must have the same count** (C4).

**Start or end?** Compare the run's first and last pulse times with the camera
log's `VC2_StartAcquisition` and `VC2_StopAcquisition` times for that run (see
"Logs"), after converting PC time to GPS time (see "Photo times"). Pulses before
StartAcquisition came before the cameras were ready; pulses after
StopAcquisition came after they stopped. Without the camera log, report the
shortfall without saying where.

**`eventOutB.txt` and `eventInA.txt`** carried the same pulses as `eventOutA`
(`eventInA` 100–160 µs later) on every run of 2026-10-17. Their roles are not
confirmed. Use them only as a technical cross-check: note any disagreement with
`eventOutA` in the technical section.

**Evidence for the pairing.** The camera log names every 100th photo with the PC
time it was processed. With photo `k` ↔ pulse `k − 1`, all 56 such lines on
2026-10-17 (19 runs) sit a steady 51.47–51.60 s after their pulse (on top of the
PC's whole-hour offset), drifting smoothly through the afternoon. Pairing photo
`k` with pulse `k` scatters them by half a second. The one outlier, `154422`, is
the run with the no-photo pulse.

### Photo times — when each photo was taken
**File dates can't be used.** On the van, a photo's file date would have been the
PC's clock when it was written. Copying destroyed that (confirmed by Derek): every
copy in the sample data has file dates days after collection, seconds apart for a
whole run. The photos have no EXIF and no time inside (just a `MTRX_NI` tag).
Never read a file date as a photo time.

Each photo's time is rebuilt from its pulse:
1. **Pulse → GPS time.** Convert the pulse's unwrapped device time with
   `utcTime.txt` from the same DataLogger folder — tab-separated, two header
   lines, columns `timestamp (us)`, `status`, `gpsTimeOfWeek`, then `year month
   day hour minute second nanosecond`, one row per second. Interpolate between the
   two rows either side.
2. **GPS time → PC time** — the time the van PC would have stamped on the file.
   Add the day's **PC-vs-GPS offset** from the `CallbackUtc` lines in
   `ARAN01-Server-SBG.log`: `Delta TSUnix PC vs HW: 3651.555 (PC ahead)`. Use the
   line nearest in time; the offset drifts (about 0.13 s over the afternoon of
   2026-10-17). Read it per day; never hard-code it. On 2026-10-17 the PC was
   **3651.6 s (1 h 0 min 51.6 s) ahead**.
   - `SBG.log` keeps only 1–2 days, so it is often missing. **Fallback:** the
     camera log's `FrameID` lines (every 100th photo, PC time + file name) give the
     same offset — the median of (logged PC time − pulse GPS time). If both
     sources exist, use `SBG.log` and report the difference in the technical
     section.
   - If neither exists, leave PC time blank and say why.
3. **GPS time → true local time** with `zoneinfo` (Eastern, DST-aware).

Photo 1, the start-up frame, has no pulse: no GPS time, flag `startup_frame`, and
if the camera log is available, give the `VC2_StartAcquisition out` time as an
approximate PC time.

**Self-check on every run.** For each camera-log `FrameID` line, compare the
logged PC time with the computed PC time for that photo. The camera log writes
each line a **steady ~0.42 s after the photo** (processing delay): on 2026-10-17
all 56 lines sat at 0.408–0.434 s. So compare each line with the **day's typical
delay** (the median), not with zero. A line more than `frame_log_tolerance_s`
(default **0.1 s**) from it means the pairing is wrong for that run — a wrong
pairing shifts lines by a whole pulse gap, at least 0.145 s: write its rows with `time_source =
"unverified"` and note it in the technical section.

`DmiStationEx <run>.csv` is **not needed** for photo times. If it is ever used,
its first rows are stamped with the PC clock (about 1 h ahead) until GPS locks,
then switch to GPS time — drop the rows before the switch.

**Per-photo list (CSV)** — `images_<signoff folder>_<timestamp>.csv` in
`_QCDATA/`, one per signoff folder, all days. One row per photo file, columns in
this order:
`day, run, view, filename, photo_number, pulse_number, pulse_device_us, gps_utc,
pc_time, local_time, time_source, gap_from_previous_s, flags`.
- `pc_time` is the closest thing to the original file-creation time. Say so in
  the CSV's header comment.
- `time_source`: `pulse`, `startup_frame`, `unverified`, `none`.
- `flags`: `startup_frame`, `after_stop`, `after_no_photo_pulse`, ...
- Written in full; never truncated.

### Logs — where they are and how to search them
- **ACS logs** are in `<day>/Logs/<PC name>/`. The PC has been `ARAN01-SERVER`
  since 2026-10-09 and was `ARANSW1-SERVER` before; files carry whichever name was
  current, in mixed case (`ARAN01-Server-SBG.log`, `AranSW1-Server-SBG.log`,
  `ARANSW1-SERVER-VideoLogCXP.log`). Match both names, ignoring case.
- **Logs rotate** as `.log`, `.log.1`, `.log.2`, ... Search all of them, and filter
  every line **by date**, not just by time of day.
- **The camera log (`<PC>-VideoLogCXP.log`) rolls over and keeps weeks.** A day's
  late runs can be in the **next** day's upload. Search the camera log in every
  day folder of the signoff folder, plus the extra log folder — not just the
  day's own.
- **`ARAN01-Server-SBG.log` keeps only 1–2 days.** Expect it to be missing for
  older days; use the FrameID fallback.
- **Extra log folder.** Logs and export logs are copied separately and may not be
  in the day folder (confirmed by Derek). The GUI has an optional **Log folder**
  picker; the CLI has `--logs <folder>`. QCDATA searches it — recursively,
  read-only — for ACS logs and run lists, as well as the day folders and
  `ExportBakFiles\`. De-duplicate identical files.
- **Camera-log lines used:** `VC2_StartAcquisition in` / `out`,
  `VC2_StopAcquisition in` (PC time, `YYYY-MM-DD HH:MM:SS,mmm`), and
  `ProcessingFunction, FrameID: <n>, EventTimeStamp: <s>, MilErr: <e>, File:
  \\...\Images\<run>\<view>\<name>.jpg` (every 100th photo). `MilErr` other
  than 0 → technical-section note.
- **SBG-log lines used:** `CallbackUtc, TS HWUnix: <s>, TS PCUnix: <s>, Delta
  TSUnix PC vs HW: <s> (PC ahead|PC behind)`.

### Lasers (GoCator) — check the rows, not just the file
Files: `GoCatorData/<run>/<run with T>L.csv` and `...R.csv` — e.g.
`GoCatorData/20261017.154422/20261017T154422L.csv`.
- Each row starts `frameIndex, timestamp` (the sensor's own clock),
  `ptpTimestamp`, `encoder`, then the profile points. Rows are very wide; read only
  the first few columns.
- **Report three cases separately** (confirmed by Derek): **missing** (no file),
  **empty** (file, no profile rows), **short** (rows stop well before the run
  ends). On 2026-10-17: none missing; `160558` L and R empty (an `X` run —
  explained); `154208` one pulse late on both sides (normal — below).
- **`frameIndex` gaps** are dropped profiles → WARN with the count. None on
  2026-10-17 across all 60 files.
- **The PTP clock can jump at the start while it locks.** Ignore jumps in the
  first rows when measuring time spans.
- **Rows are triggered by the encoder**, not by time: 136 encoder counts per row
  on 2026-10-17, and the time between rows shrinks as the van speeds up. While
  the van is stopped, few or no rows are written.
- **`ptpTimestamp` is TAI time from the SBG** (the SBG is the source — confirmed
  by Derek; TAI shown by the data). Convert to UTC as `ptpTimestamp/1e6 −
  tai_minus_utc_s`, with `tai_minus_utc_s: 37` in config (the current TAI−UTC
  difference; never hard-coded). Evidence: on 2026-10-17 the first laser row came
  36.0–36.5 s after the first camera pulse in 24 of 26 runs, i.e. about 0.9 s
  *before* the first pulse once the 37 s is removed. On GPS time (18 s) or UTC
  the lasers would start 18–36 s late in every run, which doesn't fit.
- **Check each side on its own.** Left and right can each start late or stop
  early independently (confirmed by Derek). Every laser finding names the side.
- **Measure "short" in distance, not time** — count camera pulses (one per
  0.75 m) that fall outside the laser data, using UTC on both:
  - **starts late:** pulses before the side's first laser row;
  - **stops early:** pulses after the side's last laser row.
  More than `laser_short_pulses` (default 2, ≈1.5 m — same allowance as photos)
  → WARN, e.g. "Left laser starts 6 pulses (≈4.5 m) after the cameras". Up to 2 →
  technical-section note.
- **Why not seconds:** in `20261017.154208` both lasers began 4.3 s after the first
  camera pulse — but the van paused 5.3 s right after that pulse, so only **one
  pulse (≈0.75 m)** had no laser data. A time rule called that a gap; the
  distance rule correctly calls it normal.
- **Normal on 2026-10-17 (both sides, 26 runs):** lasers start 0.4–4.2 s *before*
  the first pulse (except `154208`, one pulse after) and keep running 3.5–17 s
  *after* the last pulse while the van stops. No run had a pulse after the last
  laser row.

### QC_Video.csv — what it is, verified
Written by the collection software, one per day folder. Reverse-engineered from
the non-empty copies on 2026-10-09 (42 rows) and 2026-10-20 (4 rows), and checked
against an independent re-derivation:

- Header: `Session Name,Error,View,First File,Last File,Begin Chainage,End Chainage,Image Count`
  — sometimes with a trailing comma.
- **Every row seen is the same error, `Image missing`, and the same pattern: the
  images stop before the session's recorded end.**
  - `First File` = the **last image that exists** (e.g. `000000040500.JPG`).
  - `Last File` = the **session end distance written as a fake filename**
    (`000000066039.JPG` = 66.04 m); no such file exists.
  - `Begin Chainage` / `End Chainage` = the same two distances in **kilometres**.
  - `Image Count` ≈ the number of missing tail frames.
- An optional **9th column** holds a hand-written note
  (`File Deleted - Did not affect collection`). Preserve and display it.
- Empty (header-only) means it found nothing.

**Verification result (2026-10-28):** on 2026-10-09, all 28 session-views where
images exist matched exactly (same last image, same end, consistent count). On
2026-10-10, -13, -14, -17, and -18 it was empty, and an independent check found
no tail shortfall over 2.1 m either. **No case was found where QC_Video was
wrong.** What it does *not* detect: holes mid-run (no example exists in the
data to test either way), images extending past a zero-length export, and
photos beyond pulses + 1.

### Where the app writes — it only ever adds files
**Hard rule (confirmed by Derek): no data can change; QCDATA may only add files.**
It never modifies, renames, moves, or deletes any existing file or folder on the
data drive — collected data, logs, Dailies, `QC_Video.csv`, or its own earlier
reports. Every data-drive file is opened read-only (`"rb"` / `"r"`, never a
mode that can write).

What it adds:
- `<root>\_QCDATA\` — created if absent (the only folder QCDATA ever creates on
  the data drive). Each run adds a new set of files:
  `QCDATA_Report_<name>_<YYYYMMDD-HHMMSS>.html`,
  `findings_<name>_<YYYYMMDD-HHMMSS>.json`, and
  `images_<name>_<YYYYMMDD-HHMMSS>.csv`. `<name>` is the folder name, or for a
  drive root its volume label (else the drive letter). If a name already exists,
  append `-2`, `-3`, … — **never overwrite**. Earlier reports stay untouched.
- With `--out`, the same files go to that folder instead, under the same rules.
- If the data drive is read-only, write nothing there; say so, and offer to save
  the report to another folder.

Off the data drive, beside `QCDATA.exe` (these two are the only files QCDATA
ever rewrites):
- `config.yaml` (in the dev tree: the project root) — thresholds, `data_drives`,
  `folders`; read and written by the Settings screen.
- `qcdata_state.json` — the remembered signoff folder and log folder, nothing
  else. If the app folder is not writable, use
  `%APPDATA%\QCDATA\qcdata_state.json`. Kept separate from `config.yaml` so the
  app never rewrites a file Derek hand-edits just to remember a folder.

**Enforce it in code:** one guard function owns every write. On the data drive it
allows only *creating new files* under `_QCDATA\` (or `--out`) — opened with
exclusive-create mode (`"x"`), so an existing file can never be overwritten even
by a bug. Off the data drive it allows only the two app files above. Everything
else is refused. Unit-tested with a traversal attempt and an overwrite attempt.

## ⭐ The checks (the heart of the app)

Each check is a class behind a common `Check` interface, individually
enable/disable-able and threshold-able from `config.yaml`, returning zero or more
`Finding` objects. Each `Finding` carries: `check_id`, `severity`
(`PASS`/`WARN`/`FAIL`), `session` (or `None` for day-level), `message_plain`
(crew-facing, no jargon), `message_technical` (for Derek / the JSON), and
`what_to_do`.

| ID | Check | Default severity when it trips |
|----|-------|-------------------------------|
| **C1** | Each day folder has its Daily, and its export log can be found (day folder, root export folders, or the extra log folder) | FAIL if the Daily is missing (no run list — nothing can be checked); WARN if the export log isn't found ("choose the log folder") |
| **C2** | Runs in the export log and the Daily match | WARN on any difference, listing the runs on each side |
| **C3** | Every Daily run (`C` or `V`) has `Images/<run>/ROW`, `Images/<run>/Rear`, and `GoCatorData/<run>/` with both an `L` and an `R` csv. **FIS is never checked.** | FAIL per missing payload — **subject to the partial-copy guard** |
| **C4** | `ROW` frame count equals `Rear` frame count, per session | FAIL on mismatch |
| **C5** | No holes in the image sequence: between the first and last frame, every multiple of the derived step is present | FAIL, listing the first few missing distances |
| **C6** | Last image distance is within tolerance of the export log's `EndDistanceStamp` (the tail check — the same thing QC_Video detects) | WARN beyond `warn_m`, FAIL beyond `fail_m` — **unless the Daily explains it** (`X`, or "Collected Short") |
| **C7** | Runs on disk or in `StatusMessages` with no Daily row — not part of the day (false starts) | Information, technical section only; never raises the verdict |
| **C8** | `StatusMessages` warning/error scan, aggregated by message code | Information, technical section only. A `9057` ("frames may get lost") is shown next to that run's C15 result — if C15 found no loss, it says so; if C15 found loss, C15 already reports it |
| **C9** | `GPS Mode` in the Daily — all `NoSolution` | Information, technical section only. Blank positions are valid (confirmed by Derek) |
| **C10** | **Lasers**, per run and side: missing / empty / short reported separately; `frameIndex` gaps; L and R row counts within tolerance | FAIL missing; WARN empty; WARN `frameIndex` gaps (with count); WARN short; WARN L/R beyond tolerance |
| **C11** | **Every part present, checked separately** — copies often miss whole pieces (one copy arrived with no `SBGData/261017` DataLogger folders and without the previous day's Qinertia projects). Per day: `SBGData/<yymmdd>`, at least one Qinertia project `SBGData/<id>_0001`, the camera log. Per run: DataLogger folder | WARN per missing part, naming what it stops QCDATA from checking (e.g. "no DataLogger folder — photos can't be counted against pulses or timed"; "camera log not found — choose the log folder"). A missing `SBG.log` is **not** a WARN when the FrameID lines give the offset (technical note only); WARN only if neither source exists, because photos then get no PC time |
| **C12** | *Removed.* Photos outside the root `Images\` folder — the Morning / Mid-Day / Evening sample folders and their `ReadMe.txt` receipts — don't matter (confirmed by Derek). Not checked, not reported. The ID is not reused. | — |
| **C13** | **DEFERRED to Phase 6.** Every session/section on disk has its expected rows in the MS SQL database, and vice versa | FAIL on disk-not-in-DB; WARN on DB-not-on-disk |
| **C14** | **QC_Video verification.** Re-derive the tail shortfall per session-view (as C6) and compare it with every `QC_Video.csv` row: same session, view, last image, and end. Report agreements and disagreements | WARN on any disagreement in either direction ("QC_Video listed X, QCDATA did not" / "QCDATA found X, QC_Video did not"). Agreement is PASS and is reported as "QC_Video verified" |
| **C15** | **Dropped photos.** Per run and view, by the rules in "Camera pulses": photos vs pulses + 1, after dropping pulses less than 0.13 s after the previous one | PASS: equal, or 1–2 short at the end. WARN: short at the start, or more than 2 short. FAIL: more photos than pulses + 1. Technical section: each no-photo pulse, and any `eventOutB` / `eventInA` disagreement |
| **C16** | **Stops and time gaps** — gaps between consecutive pulses over `stop_s` | Information, listed per run with photo number and duration. Never raises the verdict — stopping is normal. Crew section shows only a count |
| **C17** | **Time sync** (technical section only): the day's PC-vs-GPS offset from `SBG.log` and/or the camera-log FrameID lines, its drift through the day, and the FrameID self-check results | Information only; never shown to the crew; never raises the verdict. Highlighted when drift within a day exceeds `clock_drift_note_s` (2 s), the two sources disagree by more than 1 s, or a self-check fails |
| — | **Sessions collected** (report section, not a check). Every Daily row: status, section, length, collected length, crew comment, initials; plus the footer metadata (software version, time in motion) | — |

### Thresholds observed in the reference data — use as defaults
Derived from all 28 sessions of 2026-10-17, and — for C6 and C14 — from every
signoff folder with images in `F:\001_BuggyData\001_RawData\100_Signoff` as of
2026-10-28. **Still provisional**; Phase 8 re-tunes against the fuller dataset.

- **C5 step:** 750 mm derived in every session. Zero holes found. The check is
  therefore expected to be quiet on good data — if it fires constantly on the
  larger dataset, the step derivation is wrong, not the data.
- **C6 end tolerance:** across all good sessions in all folders, images stopped
  short of the recorded end by at most **2.09 m**. Every real tail loss (all of
  them on 2026-10-09, all confirmed by QC_Video) was short by **11.41 m or more**.
  That is a clean separation. Defaults: `warn_m: 3.0`, `fail_m: 8.0` — both sit
  inside the gap.
- **C6 zero-end sessions:** three sessions on 2026-10-17 had
  `EndDistanceStamp = 0.00` while images extended to 25.50 m, 2.25 m, and 0.75 m.
  All three are `X` (deleted) in the Daily, so they are **explained** and must not
  warn. If a zero-end session is *not* explained by the Daily, it is its own WARN
  ("the run recorded distance but exported zero length") and must not reach the
  tolerance arithmetic.
- **C15 no-photo pulse:** `min_pulse_gap_s: 0.13` (confirmed by Derek). Normal
  gaps go down to 0.145 s at about 19 km/h. One case on 2026-10-17 (`154422`).
  `normal_end_short: 2` — up to two photos short at the end is normal.
- **C16 stop:** `stop_s: 5.0`. Typical pulse gap on 2026-10-17 was 0.35–0.65 s;
  the longest stops were 21.1 s (`151845`), 16.1 s (`160344`), 15.2 s
  (`160802`), 14.6 s (`160033`).
- **C17 / photo times:** offset on 2026-10-17 = 3651.555 s, PC ahead (from
  `SBG.log` at 11:57); the FrameID lines put it at 3651.47–3651.60 s through the
  afternoon (3651.297 s by evening). `clock_drift_note_s: 2.0`;
  `frame_log_tolerance_s: 0.1` (from the day's typical camera-log delay, ~0.42 s).
- **C10 lasers:** `laser_short_pulses: 2`; `tai_minus_utc_s: 37`. See "Lasers" for the
  normal ranges this sits outside of.
- **C10 GoCator L/R:** observed row-count differences of 1, 2, and 3 lines on a
  5 000–11 000 line file. Exact equality is **not** a valid rule.
  Default: `max_abs_diff: 25` and `max_pct_diff: 1.0`, whichever is larger.
- **C8 codes seen:** `9056` "about to reach the speed threshold" (104 rows),
  `9057` "capture interval speed limit exceeded, frames may get lost" (2 rows, run
  `165541` — and C15 shows no photos were lost there). SBG module rows include
  `ERR ... speed too high` (9) and `WARN ... epoch too far in the past`. All go to
  the technical section, aggregated by code — "9056 — 104 times", never 104 rows.
- **C9:** all 25 rows on the reference day read `NoSolution`. Technical section
  only, worded "positions may not be post-processed yet".

### Partial-copy guard (required, not optional)
Before emitting C3 findings, compute the fraction of the day's Daily runs (`C`
or `V`) with no payload folder at all. If it exceeds `partial_copy_threshold` (default `0.5`),
suppress the individual C3 findings and emit **one** day-level WARN:

> "This day looks only partly copied — 44 of 48 collection sessions have no image
> or profile data at all. If you meant to copy the whole day, copy it again. If
> this is a partial sample, nothing is wrong."

Severity is **WARN, not FAIL**, because the likeliest cause is an incomplete copy
rather than data loss, and a FAIL here would train the crew to ignore red. Record
the suppressed session list in the JSON output and in a collapsed section of the
HTML so nothing is hidden, only de-emphasized.

This behaviour must have a dedicated test on a synthetic day (48 `C` runs, 4
with photos) — the real 2026-10-16 is not a partial copy (see criterion 2).

## ⭐ Security & data handling:
Threat model, in four lines:

- **Protecting:** the integrity of collected survey data (which must never be
  modified by a QC tool), and in Phase 6 a database credential.
- **Attackers:** not adversarial humans. The realistic threats are a malformed or
  hostile **filename** or **CSV field** from the collection vehicle, a path that
  escapes the intended folder, and a leaked DB credential.
- **Trust boundaries:** every file path, filename, CSV field, and XML document
  read from the signoff folder is untrusted input. So is `config.yaml`.
- **Therefore:** validate everything crossing that boundary; write only inside
  `_QCDATA/`.

Concrete rules:
- **Only add files on the data drive.** All writes go through one guard
  function (see "Where the app writes"): new files only, under `_QCDATA\` or
  `--out`, created with exclusive-create mode `"x"`; plus the two app files
  beside the exe. Resolve paths with `Path.resolve()` and compare against those
  roots — reject `..`, symlinks pointing outside, and absolute paths from config.
  Tested with traversal and overwrite attempts.
- **Bound everything.** Service logs reach 20 MB and there are ~100 of them.
  Stream them line by line; never `read()` a log whole. The same applies to the
  SBG files QCDATA reads. From each DataLogger folder QCDATA reads only
  `eventOutA`, `eventOutB`, `eventInA`, and `utcTime` — never the large IMU,
  navigation, or raw GNSS files. Cap the number of
  findings retained per check (default 500) and say "and N more" beyond that.
- **Malformed input must not crash the app.** A bad row is a finding, not a
  traceback. Wrap each check so an unexpected exception becomes a FAIL finding
  naming the check, and the remaining checks still run. The crew must always get
  a report.
- **XML:** parse `ARAN01_Settings_*.xml` with `defusedxml` or with
  `xml.etree.ElementTree` configured against entity expansion. Do not use
  `xml.dom.minidom` or `lxml` with default settings on untrusted XML.
- **HTML report:** the report embeds filenames and log messages from untrusted
  data. **Jinja2 autoescaping must be on** (`autoescape=True` — it is *off* by
  default when not using `select_autoescape`). A filename containing `<script>`
  must render as text. Test this.
- **Phase 6 database:** credentials in a git-ignored `.env`, with a committed
  `.env.example` holding keys and no values. Connection string assembled from
  parts, never concatenated from user input. **Parameterized queries only** — no
  f-string SQL. Use a read-only DB account; least privilege. Never log the
  connection string or password; scrub them from error messages. Set a connection
  timeout and fail to "database not checked" rather than hanging.
- **Phase 6 is security-sensitive work:** strongest tier plus a human review step.
- `pip-audit` must be clean at the final gate.

## ⭐ Integrations:
- **MS SQL Server** (Phase 6, deferred) via `pyodbc` + the Microsoft ODBC Driver
  for SQL Server. Read-only. Server name, database, schema, table names, and the
  expected row grain are **all unknown at spec time** — Derek will supply them
  when the project is on a machine with access. Phase 6 begins with an
  interview, not with code.
- **Default browser** — to open the HTML report. `webbrowser.open()`.
- No other integration. No telemetry, no auto-update, no network calls.

## ⭐ Target OS and hardware:
Windows 10/11 x64. The collection laptop and Derek's workstation. Local or
network-attached drives (data has been seen on `F:\` and on UNC paths such as
`\\ARAN01-SERVER\Removable1\`). Must tolerate slow network paths: a day holds
~12 000 images, and the app walks directory listings rather than reading image
contents, so a full check should take seconds, not minutes.

Signoff folders are on **`F:\` or `G:\`** (confirmed by Derek); see the Run
screen for how remembered folders survive a drive-letter change.

**Distribution — decided (Derek, 2026-10-28): a standalone one-folder build, no
installer.** PyInstaller `--onedir` produces a `QCDATA\` folder holding
`QCDATA.exe` and its support files; ship it as `QCDATA_<version>.zip`. The crew
unzips anywhere (including a USB stick) and double-clicks `QCDATA.exe`. No
Python, no admin rights, no network. `config.yaml` ships beside the exe.
- Chosen over a one-file exe because one-file unpacks itself to a temp folder on
  every launch (slower start) and is flagged by antivirus more often.
- Expect roughly 80–150 MB, mostly Qt. Exclude unused Qt modules (WebEngine,
  Multimedia, 3D, QML, …) to keep it down.
- The exe is not code-signed, so Windows SmartScreen shows "Windows protected
  your PC" on the first launch: *More info → Run anyway*. Say so in the README.
  Company antivirus may need it allowed.
- **Phase 6 caveat:** the database check needs the Microsoft ODBC Driver for SQL
  Server installed on the machine; the exe can't carry it. If the driver is
  missing, the app must still run every file check and report "database not
  checked — ODBC driver not installed".
- `launch.bat` + `uv` stays for development only.

## ⭐ Version control and environment:
- Python **3.13** (`requires-python = ">=3.13,<3.14"`), matching `ImageQC`.
- Managed with **uv** — `pyproject.toml` + committed `uv.lock`. Not pip, not
  conda, not a bare venv.
- `launch.bat` at the project root, **for development**: double-click, `uv sync`
  on first run, then launch the GUI. Copy the pattern from
  `..\ImageQC\launch.bat`. The crew gets the one-folder exe instead.
- Git with a `.gitignore` covering `.venv/`, `.env`, `__pycache__/`,
  `_QCDATA/`, and `SampleData/` payload (sample data is large; keep the folder
  structure and a README, not 12 000 JPEGs).
- Entry points in `pyproject.toml`: `qcdata = "qcdata.cli.main:main"` and
  `qcdata-gui = "qcdata.gui.app:main"`.

## ⭐ Preferred tech stack:
Verified against the PyPI JSON API on 2026-10-28.

| Package | Version | Purpose |
|---------|---------|---------|
| Python | 3.13.x | Runtime. PySide6 requires `>=3.10,<3.16`; PyInstaller supports through 3.15. 3.13 is well-supported by both and matches `ImageQC`. |
| **PySide6-Essentials** | **6.11.3** | Desktop GUI — the official core-modules package (QtCore, QtGui, QtWidgets…), without the large Addons set; chosen in Phase 1 for a smaller install and exe. Released 2026-10-26. Ships an `abi3` wheel (`cp310-abi3-win_amd64`), so it runs on any Python ≥3.10 without rebuilding. |
| **Jinja2** | **3.1.6** | HTML report templating. Keeps report layout out of Python so it can be restyled without code changes. **Autoescaping on.** |
| **PyYAML** | **>=6,<7** | `config.yaml`. Matches `ImageQC`. Use `yaml.safe_load` only. |
| **pytest** | **9.2.0** | Test framework. Released 2026-10-27. |
| **pip-audit** | latest | Dependency vulnerability audit at the final gate. |
| **PyInstaller** | **6.22.3** | Builds the one-folder `QCDATA.exe` distribution (Phase 7). |
| **pyodbc** | **5.3.0** | MS SQL. **Phase 6 only** — do not add to dependencies before then. |
| **defusedxml** | latest | Safe XML parsing of the settings file. |

**Deliberate exclusions, with reasons:**
- **No pandas, no numpy.** `ImageQC` uses both because it does pixel math. QCDATA
  does set comparisons, counts, and sorted-integer arithmetic — the stdlib `csv`,
  `pathlib`, `statistics`, and `collections` modules cover all of it. Adding
  pandas roughly triples build size and startup time for no benefit.
- **PySide6 6.12.0 exists** (released 2026-10-08) but is numbered *above* a
  later-dated 6.11.3 patch, which indicates 6.11 is the maintained line. Prefer
  6.11.3. If the agent has reason to move to 6.12.x, say so and get confirmation.
- **No `.ui` files / Qt Designer** — see platform standards.

Compatibility confirmed: all of the above support Python 3.13 on Windows x64, and
none conflict with each other. PySide6's `abi3` wheel and PyInstaller 6.22.3's
Python 3.13 classifier were both checked directly.

## ⭐ Testing approach:
`pytest`, run in full at every phase gate. Target: the engine is testable without
Qt and without the real dataset.

- **Fixtures, not the real folder.** Build synthetic signoff folders in `tmp_path`
  — a tiny helper that writes a fake export log, status messages, and empty `.jpg`
  files at chosen distance stamps. Every check gets a happy-path test and at least
  one failing-path test from fixtures.
- **Named regression tests from the real data**, each asserting a finding
  observed in the samples:
  - `test_c7_runs_without_daily_row_are_info` — `141947`, `154142` appear only
    in the technical section and don't change the verdict.
  - `test_reference_day_verdict` — the 2026-10-17 section is PASS; `154208`'s
    one-pulse late laser start is a technical note on both sides.
  - `test_laser_short_counts_pulses_per_side` — a fixture where only the right
    side stops 5 pulses early → one WARN naming the right side; a long pause
    before the first laser row with ≤2 pulses → no WARN.
  - `test_ptp_is_tai` — with `tai_minus_utc_s: 37`, first laser rows land within
    4.2 s before the first pulse in 25 of 26 runs on 2026-10-17.
  - `test_v_status_checked_like_c` and `test_x_status_not_checked`.
  - `test_c5_clean_on_reference_day` — zero missing frames across all 28 sessions.
  - `test_c5_detects_injected_gap` — delete one frame from a fixture; it is found,
    and the reported distance is correct.
  - `test_partial_copy_guard_emits_one_finding` — a 48-session day with 4 payload
    folders yields exactly one day-level WARN, not 44 findings.
  - `test_c6_zero_end_is_special_cased` — `EndDistanceStamp = 0` with frames
    present does not reach the tolerance arithmetic.
  - `test_c8_aggregates_by_code` — 104 identical `9056` rows yield one finding.
  - `test_c10_tolerates_small_lr_difference` — a 3-line L/R difference passes.
  - `test_9057_resolved_by_pulse_check` — `165541`'s `9057` rows sit in the
    technical section beside "no photos lost"; the verdict stays PASS.
  - `test_daily_x_sessions_are_explained` — `142650`, `160558`, `161445` on
    2026-10-17 appear under "Explained by the crew", at PASS, with their comments.
  - `test_daily_footer_is_metadata` — `ACS Version ...`, `Time in motion ...`
    rows become metadata, never sessions.
  - `test_trigger_parser_handles_leading_spaces` — a file mixing ` 88753988` and
    `1050947943` rows parses every row. **Regression test for a real bug hit
    during spec research.**
  - `test_c15_plus_one_rule_reference_day` — all 30 runs on 2026-10-17 satisfy
    photos = pulses + 1 after dropping no-photo pulses.
  - `test_c15_no_photo_pulse_154422` — the pulse under 0.13 s is dropped and noted
    in the technical section.
  - `test_c15_extra_photos_fail` — more photos than pulses + 1 → FAIL.
  - `test_c15_end_short_two_is_normal` / `test_c15_start_short_warns` (start vs
    end decided from the camera log's Start/StopAcquisition).
  - `test_counter_rollover_170358` — the 32-bit rollover mid-run is unwrapped;
    `170358`'s photo times match its FrameID lines.
  - `test_pairing_frameid_selfcheck` — every FrameID line on 2026-10-17 agrees
    with the computed PC time within 0.5 s.
  - `test_pc_offset_from_sbg_log` (3651.555 s on 2026-10-17) and
    `test_pc_offset_frameid_fallback` (with `SBG.log` removed, the offset comes
    from FrameID lines and agrees within 0.2 s).
  - `test_laser_missing_empty_short_reported_separately` — includes `160558`'s
    empty files, explained as an `X` run.
  - `test_log_search` — both PC names (`ARAN01`, `ARANSW1`), any case; `.log`,
    `.log.1`, ...; filtered by date; a run whose camera log is in the next day's
    upload is still found; the extra log folder is searched.
  - `test_sbg_folder_matches_within_2s` — `154209 DataLogger` matches session
    `154208`.
  - `test_c14_agrees_with_qcvideo_20261009` — zero disagreements across all 28
    session-views with images.
  - `test_c14_detects_disagreement` — a fixture where QC_Video lists a loss that
    is not there, and one where it misses a real loss; both flagged.
  - `test_inventory_csv_one_row_per_image` — row count equals file count; no row
    ever uses a file date as a time.
  - `test_discovery_batch1` — `Zipfiles\Batch1` discovers all six days; export
    logs collected from day folders, `ExportBakFiles`, and `ExportLogs`
    (`_export_log.csv`), de-duplicated by session; Oct 16's two exports unioned;
    `ReviewData_*.csv` ignored; `.JPG` and `.jpg` both matched.
  - `test_day_without_export_log_warns` — Batch1 Oct 15 (37 Daily rows, no
    export log) is a WARN telling the user to choose the log folder; its runs are
    still checked from the Daily; pointing `--logs` at a folder holding the export
    log clears the WARN.
  - `test_non_signoff_folder_message` — a nested legacy folder gets the clear
    "doesn't look like a signoff folder" message, not a crash.
  - `test_fis_never_checked` and `test_qc_pcs_files_ignored`.
  - `test_only_adds_files` — snapshot every file on a fixture root (path, size,
    modified time, hash) before and after **two** runs: the only differences are
    new files under `_QCDATA\`; the first run's report is unchanged by the second.
  - `test_guard_refuses_overwrite` — writing to an existing name is refused; a
    name clash gets `-2`.
  - `test_drive_root_layout` — a fixture laid out like `F:\` (day folders +
    `Images`, `GoCatorData`, `SBGData` at the root, plus `$RECYCLE.BIN` and an
    unrelated folder) is discovered correctly, and so is `17thAnd16th` itself.
  - `test_newest_day_default` — with several days on the drive, only the newest
    is checked unless more are ticked or `--days` says otherwise.
  - `test_remembered_folder_drive_fallback` — a remembered `F:\...` path that no
    longer exists is found on `G:\` and the user is told; neither existing → empty
    field, picker opens on the first existing drive.
  - `test_state_file_never_touches_config` — remembering a folder writes only
    `qcdata_state.json`.
- **Security tests:** write-path traversal is refused; a filename containing
  `<script>` is escaped in the HTML report; a 20 MB log is streamed, not read
  whole.
- **GUI tests:** offscreen smoke test (`QT_QPA_PLATFORM=offscreen`) — the window
  constructs, the three tabs exist, the worker thread completes, the verdict
  banner shows the right state. Follow `ImageQC`'s precedent.
- **Determinism test:** two consecutive runs on the same fixture produce identical
  findings JSON (timestamps excluded).

## ⭐ Preferences and tradeoffs:
- **Fewer, better findings beats completeness.** A quiet report that the crew
  trusts catches more than a noisy one they skip. Aggregate; use the partial-copy
  guard; prefer one good sentence to five technical ones.
- **Three states, and WARN means "a human should look".** Reserve FAIL for data
  that is certainly missing. Anything ambiguous — a partial copy, a warning that
  fired without loss, missing post-processing — is WARN. Derek's prior app
  (`ProjectCompare`) uses the same red/yellow split, and `ReverseRunProcessor`
  established that a condition the app already handled correctly must not be
  reported as a warning. Carry that principle here: **do not warn about something
  the check itself has already proven fine.**
- **Thresholds in config, not code.** Derek expects to tune them against the
  fuller dataset without a rebuild.
- **Plain language is a hard requirement**, not polish. If a message needs a
  glossary, rewrite it.
- **Deterministic and add-only** over clever.
- Prefer the stdlib. Every dependency must justify itself.

## ⭐ Reference material:
- **`SampleData\17thAnd16th\`** — two partial collection days. The 2026-10-17 day
  (28 sessions, full payload) is the **reference day** for all expected-behavior
  tests. The 2026-10-16 day (48 exported runs; 44 marked `X` by the crew; the 4
  `C` runs all have photos) tests the explained-by-the-crew handling. Source: `F:\001_BuggyData\001_RawData\100_Signoff\17thAnd16th`.
  Treat as read-only input, never a deliverable.
- **The other signoff folders** in `F:\001_BuggyData\001_RawData\100_Signoff` —
  `2024_14_Runs`, `2024_15_Runs`, `20261009_Signoff`, `20261009_New_Reverse_run`,
  `20261009_NeW_Reverse_Run_Tape`, `20261010_Signoff`, `20261013_Signoff`,
  `20261016_Evening`, `20261018_Afternoon`, `20261020 2`, and `Zipfiles\Batch1`.
  **`Zipfiles\Batch1` is the multi-day reference** — the standard layout with
  six days, including a day with no run list (Oct 15), a day exported twice
  (Oct 16), a day with no logs (Oct 14), and no Qinertia projects at all. The others are the **QC_Video verification corpus** for C14; some
  use an older nested layout that the app does not need to support — for C14
  tests, copy the needed sessions into a standard-layout fixture. The two 2026-10-09 reverse-run
  folders are the only ones where QC_Video reported real losses with the images
  present — the reference positive case for C14. Read-only.
- **`..\ImageQC\`** — the sibling app. Copy its conventions: project layout,
  `launch.bat`, `pyproject.toml` shape, `CONTEXT.md` style, three-layer
  core/cli/gui split, offscreen GUI smoke test. Read its `CONTEXT.md` before
  starting.
- **`..\..\095_WhatMyAppDoes\`** — house convention is one `<AppName>.md` per app
  describing what it does. Write `QCDATA.md` there at Phase 7. Derek prefers
  these written **from the actual source code**, not from the README.

### Known reference gaps — must be closed before the phase that needs them
1. **MS SQL details** (blocks Phase 6): server, database, schema, table and column
   names, the expected row grain (per session? per section? per image?), and
   read-only credentials. Phase 6 cannot start without these.
2. **Fuller dataset** (affects Phase 8 tuning): Derek is supplying more collection
   days. All thresholds above are provisional until re-checked against it.
3. **What made Derek suspect QC_Video** (affects C14 tests): no case of QC_Video
   being wrong was found. If Derek has a specific day or session in mind, that is
   the most valuable C14 test case. Also: the images for the four 2026-10-20
   QC_Video rows (sessions `121954`, `143745`) and for 14 of the 2026-10-09 rows
   are not in any signoff copy, so those rows are unverified.
4. **Mid-run holes are untested everywhere.** No session in any folder has one, so
   neither C5 nor QC_Video's handling of them has been exercised on real data.
   Phase 8: build a test copy with a frame deleted mid-run.
5. **Meaning of `eventOutB` and `eventInA`** — not confirmed; used only as a
   technical cross-check, so low priority.
6. **Which Qinertia project covers which run** (affects C11 detail): projects are
   `SBGData/<id>_0001`, one per SBG session, not per run. Phase 2: work out each
   project's time span (e.g. from its `job.json`) to tell whether every run is
   covered. Until then, C11 checks only that each day has at least one.

Closed on 2026-10-28 (confirmed by Derek): **FIS** is not used — never check
it. **`QC_Pcs_Files.csv`** is obsolete (PCS is now SBG) — ignore it.
**Only add files** on the data drive — never change anything. **Data at the drive
root** (`F:\` or `G:\`). **Packaging:** standalone one-folder zip, no installer. **Remembered folders**
on `F:\`/`G:\`. **`ExportDataFiles\`** — not checked. **`ptpTimestamp`** comes from the SBG and
runs on TAI. **Lasers** are checked per side; L and R can each start late or stop
early. **Photo ↔ pulse pairing:** photo 1 is a
start-up frame with no pulse; photo `k` ↔ pulse `k − 1` (also confirmed against
56 camera-log lines). **Runs with no Daily row** are not part of the day.
**Daily `V`** = verification, checked like `C`. QCDATA must never write to
`QC_Video.csv` or `QC_Pcs_Files.csv`.

---

## Rules for the coding agent

- **Read the bundled platform standards files named above before writing any
  code**, and follow them exactly.
  - GUI desktop: always dark mode; every QWidget subclass uses the 5-method
    `__init__` pattern (`_create_widgets`, `_create_layouts`, `_connect_signals`,
    `_apply_styles`, `_load_initial_state`); every widget has a named instance
    variable; no business logic in `_create_*` methods; dynamic widgets use
    factory + populate + clear.
  - CLI: follow the structure, error-handling, and exit-code rules in
    `cli-api-standards.md`.
  - Security: follow `security-standards.md` for all file, path, input, and
    database work.
- **Read `CONTEXT.md` at the project root first** to orient.
- Ask if anything is unclear BEFORE starting — never assume silently. The reference
  gaps above are known unknowns; do not invent answers to them.
- Never delete or overwrite existing files without explicit confirmation.
- List required software and versions per phase.
- Between phases: run the full test suite, report results, and wait for
  "proceed". Do not advance if any test fails. Each phase must leave the codebase
  runnable. The proceed decision is made at the strongest tier, not delegated.
- Never work on two interdependent files simultaneously.
- If a dependency cannot be installed or versions conflict, STOP and report the
  exact error before continuing.
- If unsure whether a library is current or deprecated, web-search to verify
  before using it — version knowledge goes stale.
- No AI-generated placeholder data in production logic. No invented thresholds:
  every number in the code traces to this spec or to `config.yaml`.
- Keep secrets in a git-ignored `.env` — never hard-code them. Validate and
  sanitize all external input.
- **Do not write to the source data folder.** Ever. All output goes to `_QCDATA/`.

## Agent routing hints (capability-based, with named defaults)

Route by capability tier so cost is saved on trivial work. The strongest tier is
the default and the supervisor. Model names change — pair the tier with the
current default model so this still works if a name goes stale.

*Model names as of 2026-10-28. The spec-builder skill's own table was last
verified in July 2026 and had gone stale (it listed Claude Sonnet 5 and Claude
Haiku 4.5); the table below is the corrected current lineup. If this spec is much
older than its date above, confirm the names before relying on them.*

| Tier | Default model | Model string | Use for |
|------|---------------|--------------|---------|
| **Strongest** | **Claude Opus 5.5** (or Claude Opus 5) | `claude-opus-5-5` / `claude-opus-5` | Architecture, spec review, security review, the Phase 6 database work, complex/cross-file debugging, phase-gate decisions |
| **Mid** | **Claude Sonnet 5.5** | `claude-sonnet-5-5` | Feature implementation, boilerplate, refactoring, test writing |
| **Cheapest** | **Claude Haiku 5.5** | `claude-haiku-5-5` | Renames, formatting, trivial one-line edits, mechanical lookups |

- **When in doubt, use the strongest tier.** Lesser tiers take only genuinely
  trivial, easily-verified work.
- **Escalate on doubt.** If a lesser tier produces anything questionable, or a
  task is harder than it looked, hand it to the strongest tier.
- **The strongest tier owns every phase gate** and all security-sensitive work.
- GUI layout generation and any security-sensitive change get a human review step
  before proceeding.

## First tasks when coding begins

1. Read `CONTEXT.md` at the project root to orient — what each folder holds, which
   reference material is authoritative, what to ignore, and what is sample input
   vs. deliverable. Keep `CONTEXT.md` current as reference files are added or
   versions change.
2. Read `Specs/gui-coding-standards.md`, `Specs/cli-api-standards.md`, and
   `Specs/security-standards.md`.
3. Read `..\ImageQC\CONTEXT.md` and its `pyproject.toml` and `launch.bat` to match
   house conventions.
4. Read and list all required software, libraries, and extensions.
5. Web-search to verify current stable versions and mutual compatibility — the
   versions in this spec were verified on 2026-10-28 and may have moved.
6. Confirm the project folder exists; create subfolders as needed.
7. Create the environment with `uv` and install all dependencies.
8. Set up the `.env.example` scaffold (no real secrets committed).
9. Report setup complete with a version summary, then wait for "proceed" before
   writing any application code.
