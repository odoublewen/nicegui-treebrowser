"""Unit tests for the filename-to-preview-kind registry."""

from __future__ import annotations

from pathlib import Path

import pytest
from pygments.lexers import get_lexer_by_name

from nicegui_treebrowser import filetypes


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("picture.png", "image"),
        ("photo.JPEG", "image"),
        ("animation.gif", "image"),
        ("favicon.ico", "image"),
        ("report.pdf", "pdf"),
        ("REPORT.PDF", "pdf"),
        ("song.mp3", "audio"),
        ("voice.flac", "audio"),
        ("clip.mp4", "video"),
        ("clip.MOV", "video"),
        ("data.csv", "table"),
        ("data.tsv", "table"),
        ("README.md", "markdown"),
        ("notes.markdown", "markdown"),
        ("script.py", "code"),
        ("config.yaml", "code"),
        ("notes.txt", "code"),
        ("Dockerfile", "code"),
        ("makefile", "code"),
        ("LICENSE", "code"),
        ("archive.tar.gz", "none"),
        ("scan.tiff", "none"),
        ("photo.heic", "none"),
        ("movie.mkv", "none"),
        ("blob.bin", "none"),
        ("mystery", "none"),
    ],
)
def test_classify(name: str, kind: str) -> None:
    assert filetypes.classify(Path(name)) == kind


@pytest.mark.parametrize("name", ["vector.svg", "page.html", "index.HTML"])
def test_svg_and_html_are_shown_as_source_not_rendered(name: str) -> None:
    """Rendering them would execute their scripts in the app's own origin."""
    assert filetypes.classify(Path(name)) == "code"


def test_classify_is_case_insensitive_about_suffixes() -> None:
    assert filetypes.classify(Path("A.PnG")) == filetypes.classify(Path("a.png"))


@pytest.mark.parametrize(
    ("name", "language"),
    [
        ("script.py", "python"),
        ("app.JS", "javascript"),
        ("style.scss", "scss"),
        ("notes.log", "text"),
        ("Dockerfile", "docker"),
        ("Makefile", "make"),
        ("vector.svg", "xml"),
        ("mystery", "text"),
    ],
)
def test_code_language(name: str, language: str) -> None:
    assert filetypes.code_language(Path(name)) == language


def test_every_language_name_is_a_real_pygments_lexer() -> None:
    """ui.code highlights through markdown2 + Pygments, so the names must resolve."""
    names = set(filetypes.CODE_LANGUAGES.values()) | set(
        filetypes.STEM_LANGUAGES.values()
    )
    for name in sorted(names):
        get_lexer_by_name(name)


def test_table_delimiter() -> None:
    assert filetypes.table_delimiter(Path("d.csv")) == ","
    assert filetypes.table_delimiter(Path("d.tsv")) == "\t"
    assert filetypes.table_delimiter(Path("d.unknown")) == ","


@pytest.mark.parametrize(
    ("name", "icon"),
    [
        ("picture.png", "image"),
        ("report.pdf", "picture_as_pdf"),
        ("song.mp3", "audio_file"),
        ("clip.mp4", "video_file"),
        ("data.csv", "table_chart"),
        ("README.md", "article"),
        ("script.py", "description"),
        ("blob.bin", "insert_drive_file"),
    ],
)
def test_icon_for(name: str, icon: str) -> None:
    assert filetypes.icon_for(Path(name)) == icon


def test_registries_are_extensible() -> None:
    """Applications are expected to add their own suffixes at import time."""
    filetypes.CODE_LANGUAGES[".ino"] = "cpp"
    try:
        assert filetypes.classify(Path("sketch.ino")) == "code"
        assert filetypes.code_language(Path("sketch.ino")) == "cpp"
    finally:
        del filetypes.CODE_LANGUAGES[".ino"]
    assert filetypes.classify(Path("sketch.ino")) == "none"
