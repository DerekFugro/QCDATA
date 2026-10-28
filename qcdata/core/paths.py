"""The one place QCDATA writes files. It only ever ADDS files.

Rule (confirmed by Derek): no data can change. On the data drive QCDATA may only
create NEW files, inside one output folder (default <root>\\_QCDATA\\). Files are
created with exclusive-create mode, so even a bug can't overwrite one; a name
clash gets -2, -3, ... Off the data drive, only the app's own config.yaml and
qcdata_state.json may be rewritten. Everything else is refused.
"""

from __future__ import annotations

import os
from pathlib import Path

OUTPUT_DIR_NAME = "_QCDATA"


class WriteRefused(PermissionError):
    """A write that would break the add-only rule."""


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


class WriteGuard:
    def __init__(self, data_root: Path, out_dir: Path | None = None, app_files: list[Path] | None = None):
        self.data_root = Path(data_root).resolve()
        target = Path(out_dir) if out_dir else self.data_root / OUTPUT_DIR_NAME
        self.out_dir = target.resolve()
        self.app_files = {Path(p).resolve() for p in (app_files or [])}
        self._out_dir_ready = False

    def _check_name(self, filename: str) -> None:
        if not filename or filename != Path(filename).name or filename in (".", "..") \
                or any(c in filename for c in '<>:"/\\|?*') or filename.startswith("."):
            raise WriteRefused(f"Refused: {filename!r} is not a plain file name.")

    def _ensure_out_dir(self) -> None:
        if self._out_dir_ready:
            return
        if self.out_dir.exists():
            if self.out_dir.is_symlink() or not self.out_dir.is_dir():
                raise WriteRefused(f"Refused: {self.out_dir} is not a normal folder.")
        else:
            # Creating the output folder is the only change QCDATA makes to the drive's folders.
            self.out_dir.mkdir(parents=False, exist_ok=False)
        self._out_dir_ready = True

    def create_new(self, filename: str, data: bytes) -> Path:
        """Create a NEW file in the output folder. Never overwrites; clashes get -2, -3, ..."""
        self._check_name(filename)
        self._ensure_out_dir()
        stem, suffix = os.path.splitext(filename)
        for n in range(1, 1000):
            name = filename if n == 1 else f"{stem}-{n}{suffix}"
            path = (self.out_dir / name).resolve()
            if not _is_within(path, self.out_dir):
                raise WriteRefused(f"Refused: {name!r} would land outside {self.out_dir}.")
            try:
                with open(path, "xb") as fh:      # exclusive create: fails if it exists
                    fh.write(data)
                return path
            except FileExistsError:
                continue
        raise WriteRefused(f"Refused: too many files named like {filename!r}.")

    def rewrite_app_file(self, path: Path, data: bytes) -> Path:
        """Rewrite one of the app's own files (config.yaml, qcdata_state.json) - nothing else."""
        resolved = Path(path).resolve()
        if resolved not in self.app_files:
            raise WriteRefused(f"Refused: {path} is not one of QCDATA's own settings files.")
        if _is_within(resolved, self.data_root):
            raise WriteRefused(f"Refused: {path} is on the data drive.")
        tmp = resolved.with_name(resolved.name + ".tmp")
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, resolved)
        return resolved
