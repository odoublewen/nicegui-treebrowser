"""Shared fixtures: a sample directory holding one file of every kind we preview."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

pytest_plugins = ["nicegui.testing.user_plugin"]

# a genuine 1x1 transparent PNG, so the browser would really render it
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE"
    "hQGAhKmMIQAAAABJRU5ErkJggg=="
)

MINIMAL_PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 72 72]>>endobj
trailer<</Root 1 0 R>>
%%EOF
"""


@pytest.fixture
def sample_tree(tmp_path: Path) -> Path:
    """Build a directory covering every preview kind, plus a few edge cases."""
    root = tmp_path / "sample"
    (root / "logs").mkdir(parents=True)
    (root / "empty").mkdir()

    (root / "README.md").write_text("# Sample\n\nSome *markdown*.\n")
    (root / "script.py").write_text("print('hello from script')\n")
    (root / "data.csv").write_text("name,score\nada,42\ngrace,99\n")
    (root / "table.tsv").write_text("a\tb\n1\t2\n")
    (root / "vector.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>\n')
    (root / "page.html").write_text("<html><body>hi</body></html>\n")
    (root / "Dockerfile").write_text("FROM python:3.14-slim\n")
    (root / "plain").write_text("just text, no suffix at all\n")
    (root / "picture.png").write_bytes(PNG_BYTES)
    (root / "doc.pdf").write_bytes(MINIMAL_PDF)
    (root / "song.mp3").write_bytes(b"ID3\x03\x00\x00\x00" + b"\x00" * 64)
    (root / "clip.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    (root / "blob.bin").write_bytes(bytes(range(256)))
    (root / ".hidden.txt").write_text("secret\n")
    (root / "logs" / "run.log").write_text("started\nfinished\n")
    return root


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the ``main_file`` ini option NiceGUI's user plugin reads.

    NiceGUI 3.0.x reads it without registering it, which makes the `user`
    fixture raise. Registering it here is harmless on the versions that do
    register it, since pytest lets a later definition replace an earlier one.
    """
    parser.addini(
        "main_file",
        "NiceGUI main file; empty means pages are declared by the tests themselves",
        default="",
    )
