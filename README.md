# QCDATA

Checks a sidewalk collection drive (`F:\` or `G:\`, or a copy of one) for missing
or incomplete data - photos, lasers, SBG, logs - and writes a plain-language
PASS / WARN / FAIL report. It only ever **adds** files; it never changes data.

**Status:** Phase 1 (environment) complete. Nothing checks data yet.

## Development

- Double-click `launch.bat` (sets up the environment with `uv` on first run).
- Or: `uv run qcdata version`, `uv run pytest`.

The spec is in `Specs/QCDATA_Instructions.md`; the build plan in
`Specs/QCDATA_Phase.md`; orientation in `CONTEXT.md`.

The full README (usage, exit codes, settings) is written in Phase 4.
