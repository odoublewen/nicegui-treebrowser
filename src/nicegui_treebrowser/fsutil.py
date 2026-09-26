"""Filesystem helpers: sizing, safe text reads and folder archives.

Deliberately stdlib-only, so the package depends on nothing but NiceGUI itself.
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

__all__ = [
    "get_dir_size",
    "looks_like_text",
    "make_tarball",
    "natural_size",
    "read_text",
]

_UNITS = ("kB", "MB", "GB", "TB", "PB", "EB")


def natural_size(size: int) -> str:
    """Format a byte count using decimal units, e.g. ``1.5 kB`` or ``2.3 MB``."""
    if size < 1000:
        return f"{size} byte" if size == 1 else f"{size} bytes"
    value = float(size)
    for unit in _UNITS:
        value /= 1000.0
        if value < 1000.0 or unit == _UNITS[-1]:
            return f"{value:.1f} {unit}"
    raise AssertionError("unreachable")  # pragma: no cover


def make_tarball(directory: str, arcname: str) -> bytes:
    """Return *directory* as an in-memory gzipped tarball."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        archive.add(directory, arcname=arcname)
    return buffer.getvalue()


def read_text(path: Path, limit: int) -> tuple[str, bool]:
    """Read at most *limit* bytes of *path* as text.

    Returns the decoded text and whether the file continued past the limit.
    Undecodable bytes become replacement characters rather than raising.
    """
    with open(path, "rb") as handle:
        raw = handle.read(limit + 1)
    content = raw[:limit].decode("utf-8", errors="replace")
    is_truncated = len(raw) > limit
    return content, is_truncated


def looks_like_text(path: Path, probe: int = 8192) -> bool:
    """Guess whether *path* holds UTF-8 text, by sniffing its first *probe* bytes.

    A NUL byte means binary. A decode error at the very end of the probe is
    ignored, since a multi-byte character may simply straddle the cut.
    """
    try:
        with open(path, "rb") as handle:
            head = handle.read(probe)
    except OSError:
        return False
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as error:
        # tolerate a character chopped in half by the probe boundary
        return len(head) == probe and error.start >= probe - 4
    return True


def get_dir_size(directory: Path) -> tuple[int, int, int]:
    """Return directory's file count, directory count, and total bytes."""
    files = directories = total = 0
    for entry in directory.rglob("*"):
        if entry.is_symlink():
            continue
        if entry.is_dir():
            directories += 1
        elif entry.is_file():
            files += 1
            total += entry.stat().st_size
    return files, directories, total
