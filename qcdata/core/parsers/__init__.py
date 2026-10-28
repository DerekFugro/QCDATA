"""One module per file format. Parsers read; they never judge.

Every file is opened read-only. A line a parser can't use becomes a `Skipped`
record (and a log message) - never an exception - so one bad line can't stop a
report.
"""
