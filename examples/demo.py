"""Run the browser against a generated sample directory.

    uv run python examples/demo.py          # strict allowlist (the default)
    uv run python examples/demo.py --sniff  # also preview unrecognised text files

Then open http://localhost:8080.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

from nicegui import ui

from nicegui_treebrowser import TreeBrowser

SAMPLE = Path(__file__).parent / "sample"

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE"
    "hQGAhKmMIQAAAABJRU5ErkJggg=="
)

PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj
trailer<</Root 1 0 R>>
%%EOF
"""


def build_sample() -> None:
    """Create a directory with one file of most previewable kinds."""
    (SAMPLE / "reports").mkdir(parents=True, exist_ok=True)
    (SAMPLE / "empty").mkdir(exist_ok=True)

    (SAMPLE / "README.md").write_text(
        "# Sample tree\n\nPick something on the left.\n\n- images\n- PDFs\n- tables\n"
    )
    (SAMPLE / "settings.yaml").write_text("debug: true\nthreads: 4\n")
    (SAMPLE / "analysis.py").write_text(
        "from pathlib import Path\n\n\ndef main() -> None:\n"
        '    print(sorted(Path(".").glob("*")))\n'
    )
    (SAMPLE / "results.csv").write_text(
        "sample,score,note\n"
        + "".join(f"S{i:03d},{i * 7 % 100},row {i}\n" for i in range(200))
    )
    (SAMPLE / "matrix.tsv").write_text("gene\tcount\nTP53\t120\nBRCA1\t44\n")
    (SAMPLE / "logo.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80">'
        '<circle cx="40" cy="40" r="36" fill="teal"/></svg>\n'
    )
    (SAMPLE / "Dockerfile").write_text(
        "FROM python:3.14-slim\nRUN pip install nicegui\n"
    )
    (SAMPLE / "changelog").write_text("0.1.0 - first cut, no suffix on this file\n")
    (SAMPLE / "pixel.png").write_bytes(PNG)
    (SAMPLE / "reports" / "summary.pdf").write_bytes(PDF)
    (SAMPLE / "reports" / "run.log").write_text("started\nworking\nfinished\n")
    (SAMPLE / "opaque.bin").write_bytes(bytes(range(256)) * 8)


def main() -> None:
    build_sample()
    sniff = "--sniff" in sys.argv

    @ui.page("/")
    def index() -> None:
        ui.label("nicegui-treebrowser demo").classes("text-2xl font-medium px-6 pt-6")
        ui.label(f"sniff_text={sniff} — restart with --sniff to flip it").classes(
            "text-sm text-gray-500 px-6"
        )
        TreeBrowser(SAMPLE, title="Sample tree", focus="README.md", sniff_text=sniff)

    ui.run(title="TreeBrowser demo", reload=False)


main()
