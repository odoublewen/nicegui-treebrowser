"""Unit tests for the stdlib-only filesystem helpers."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from nicegui_treebrowser.fsutil import (
    get_dir_size,
    looks_like_text,
    make_tarball,
    natural_size,
    read_text,
)


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, "0 bytes"),
        (1, "1 byte"),
        (2, "2 bytes"),
        (999, "999 bytes"),
        (1000, "1.0 kB"),
        (1500, "1.5 kB"),
        (999_999, "1000.0 kB"),
        (1_000_000, "1.0 MB"),
        (2_300_000, "2.3 MB"),
        (1_000_000_000, "1.0 GB"),
        (1_000_000_000_000, "1.0 TB"),
    ],
)
def test_natural_size(size: int, expected: str) -> None:
    assert natural_size(size) == expected


def test_natural_size_saturates_at_the_largest_unit() -> None:
    assert natural_size(10**25).endswith(" EB")


def test_read_text_reports_truncation(tmp_path: Path) -> None:
    target = tmp_path / "long.txt"
    target.write_text("abcdefghij")

    assert read_text(target, 100) == ("abcdefghij", False)
    assert read_text(target, 4) == ("abcd", True)
    # a file exactly at the limit is complete, not truncated
    assert read_text(target, 10) == ("abcdefghij", False)


def test_read_text_replaces_undecodable_bytes(tmp_path: Path) -> None:
    target = tmp_path / "latin.txt"
    target.write_bytes(b"caf\xe9")

    content, truncated = read_text(target, 100)
    assert content == "caf�"
    assert truncated is False


def test_looks_like_text_accepts_utf8(tmp_path: Path) -> None:
    target = tmp_path / "notes"
    target.write_text("héllo wörld\nsecond line\n")
    assert looks_like_text(target) is True


def test_looks_like_text_rejects_nul_bytes(tmp_path: Path) -> None:
    target = tmp_path / "blob.bin"
    target.write_bytes(b"text then\x00binary")
    assert looks_like_text(target) is False


def test_looks_like_text_rejects_invalid_utf8(tmp_path: Path) -> None:
    target = tmp_path / "latin.txt"
    target.write_bytes(b"caf\xe9 " * 10)
    assert looks_like_text(target) is False


def test_looks_like_text_tolerates_a_character_split_by_the_probe(
    tmp_path: Path,
) -> None:
    # 'é' is two bytes; land the probe boundary right between them
    target = tmp_path / "split.txt"
    target.write_bytes(b"a" * 9 + "é".encode() + b"more text here")
    assert looks_like_text(target, probe=10) is True


def test_looks_like_text_on_missing_file(tmp_path: Path) -> None:
    assert looks_like_text(tmp_path / "nope") is False


def test_get_dir_size_counts_files_folders_and_bytes(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.txt").write_bytes(b"x" * 10)
    (tmp_path / "sub" / "b.txt").write_bytes(b"y" * 5)

    assert get_dir_size(tmp_path) == (2, 1, 15)


def test_get_dir_size_ignores_symlinks(tmp_path: Path) -> None:
    (tmp_path / "real.txt").write_bytes(b"x" * 10)
    (tmp_path / "link.txt").symlink_to(tmp_path / "real.txt")

    assert get_dir_size(tmp_path) == (1, 0, 10)


def test_make_tarball_round_trips(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "hello.txt").write_text("hello")

    data = make_tarball(str(tmp_path), "bundle")

    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        names = archive.getnames()
        assert "bundle/sub/hello.txt" in names
        member = archive.extractfile("bundle/sub/hello.txt")
        assert member is not None
        assert member.read() == b"hello"
