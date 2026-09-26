"""Maps a filename to the way its contents should be previewed.

Every table below is a plain module-level dict or set, so an application can
extend them at import time, e.g. ``filetypes.CODE_LANGUAGES[".ino"] = "cpp"``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

__all__ = [
    "AUDIO_SUFFIXES",
    "CODE_LANGUAGES",
    "IMAGE_SUFFIXES",
    "MARKDOWN_SUFFIXES",
    "PDF_SUFFIXES",
    "STEM_LANGUAGES",
    "TABLE_DELIMITERS",
    "VIDEO_SUFFIXES",
    "PreviewKind",
    "classify",
    "code_language",
    "icon_for",
    "table_delimiter",
]

PreviewKind = Literal[
    "image", "pdf", "audio", "video", "table", "markdown", "code", "none"
]

#: Suffixes every mainstream browser can decode in an ``<img>`` tag.
#: Formats they cannot (``.tif``, ``.psd``, ``.heic``) are left download-only.
IMAGE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".avif",
    ".ico",
}

PDF_SUFFIXES = {".pdf"}

AUDIO_SUFFIXES = {".mp3", ".wav", ".ogg", ".oga", ".m4a", ".flac", ".aac"}

VIDEO_SUFFIXES = {".mp4", ".webm", ".ogv", ".mov"}

TABLE_DELIMITERS = {
    ".csv": ",",
    ".tsv": "\t",
}

MARKDOWN_SUFFIXES = {".md", ".markdown"}

#: Suffix to Pygments lexer name. ``.svg`` and ``.html`` are here on purpose:
#: both are served from the app's own origin, so rendering them would run any
#: script they carry. Showing the source is safe and still useful.
CODE_LANGUAGES = {
    ".bash": "bash",
    ".c": "c",
    ".cfg": "ini",
    ".config": "text",
    ".cpp": "cpp",
    ".css": "css",
    ".diff": "diff",
    ".go": "go",
    ".h": "c",
    ".hpp": "cpp",
    ".html": "html",
    ".ini": "ini",
    ".java": "java",
    ".jl": "julia",
    ".js": "javascript",
    ".json": "json",
    ".jsx": "jsx",
    ".kt": "kotlin",
    ".log": "text",
    ".lua": "lua",
    ".patch": "diff",
    ".php": "php",
    ".pl": "perl",
    ".py": "python",
    ".r": "r",
    ".rb": "ruby",
    ".rs": "rust",
    ".scala": "scala",
    ".scss": "scss",
    ".sh": "bash",
    ".sql": "sql",
    ".svg": "xml",
    ".swift": "swift",
    ".tex": "tex",
    ".toml": "toml",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".txt": "text",
    ".vue": "html",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".zsh": "bash",
}

#: Well-known files that carry no suffix at all, keyed by lowercased name.
STEM_LANGUAGES = {
    "authors": "text",
    "changelog": "text",
    "dockerfile": "docker",
    "gemfile": "ruby",
    "justfile": "make",
    "license": "text",
    "makefile": "make",
    "notice": "text",
    "rakefile": "ruby",
    "readme": "text",
}


def classify(path: Path) -> PreviewKind:
    """Return how *path* should be previewed, or ``"none"`` if we do not know."""
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in PDF_SUFFIXES:
        return "pdf"
    if suffix in AUDIO_SUFFIXES:
        return "audio"
    if suffix in VIDEO_SUFFIXES:
        return "video"
    if suffix in TABLE_DELIMITERS:
        return "table"
    if suffix in MARKDOWN_SUFFIXES:
        return "markdown"
    if suffix in CODE_LANGUAGES or path.name.lower() in STEM_LANGUAGES:
        return "code"
    return "none"


def code_language(path: Path) -> str:
    """Return the Pygments lexer name for *path*, defaulting to plain text."""
    suffix = path.suffix.lower()
    if suffix in CODE_LANGUAGES:
        return CODE_LANGUAGES[suffix]
    return STEM_LANGUAGES.get(path.name.lower(), "text")


def table_delimiter(path: Path) -> str:
    """Return the column delimiter for a tabular file, defaulting to a comma."""
    return TABLE_DELIMITERS.get(path.suffix.lower(), ",")


_ICONS: dict[PreviewKind, str] = {
    "image": "image",
    "pdf": "picture_as_pdf",
    "audio": "audio_file",
    "video": "video_file",
    "table": "table_chart",
    "markdown": "article",
    "code": "description",
    "none": "insert_drive_file",
}


def icon_for(path: Path) -> str:
    """Return the Material icon name that suits *path*."""
    return _ICONS[classify(path)]
