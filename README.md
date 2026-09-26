# nicegui-treebrowser

[![tests](https://github.com/odoublewen/nicegui-treebrowser/actions/workflows/tests.yml/badge.svg?branch=develop)](https://github.com/odoublewen/nicegui-treebrowser/actions/workflows/tests.yml)

A [NiceGUI](https://nicegui.io) element that renders a server-side directory as a
browsable tree, previews the files it finds, and lets people download them
individually or as a `.tar.gz`.

It is an ordinary NiceGUI element: it renders where you create it and accepts
`.classes()`, `.style()`, `.props()` and `.move()` like anything else in `ui.*`.

## Install

```bash
pip install nicegui-treebrowser     # or: uv add nicegui-treebrowser
```

### Supported versions

| Python | NiceGUI |
|---|---|
| 3.13 | 2.14+ or 3.x |
| 3.14 | 3.0.4+ |

NiceGUI releases before 3.0.4 pull in a `vbuild` that calls `pkgutil.find_loader`,
removed in Python 3.14, so they cannot be imported there at all. The dependency
markers pick a workable floor for you.

Python 3.15 is not supported yet: `aiohttp`, which NiceGUI requires, has no 3.15
wheels. Nothing in this package stands in the way — it should work as soon as the
wheels land.

The test suite runs against NiceGUI 2.14.1, 3.0.4 and 3.17.1.

## Quickstart

```python
from nicegui import ui
from nicegui_treebrowser import TreeBrowser


@ui.page("/")
def index() -> None:
    TreeBrowser("/srv/results", title="Results")


ui.run()
```

## Options

| Parameter | Default | Meaning |
|---|---|---|
| `root` | — | Directory to expose. Nothing outside it is ever served. |
| `focus` | `None` | File or folder to reveal and open on load. |
| `title` | `"Files"` | Heading shown above the tree. |
| `show_hidden` | `False` | Include dot-files and dot-directories. |
| `exclude` | `None` | Predicate returning `True` for paths to leave out. |
| `max_preview_bytes` | `1_000_000` | Largest text preview loaded into the browser. |
| `max_table_rows` | `5000` | Row cap for `.csv`/`.tsv` previews. |
| `allow_archive` | `True` | Show the "Download all" and per-folder archive buttons. |
| `show_full_path` | `True` | Print the root's absolute path under the title. |
| `sniff_text` | `False` | Preview unrecognised files that look like UTF-8 text. |

Two methods are worth knowing:

- `browser.focus(path)` — select `path` and expand only the folders needed to reveal
  it. Returns `False` if the path is outside the root or not in the tree.
- `browser.refresh()` — re-read the tree from disk.

## What gets previewed

| Kind | Extensions |
|---|---|
| Image | `.png` `.jpg` `.jpeg` `.gif` `.webp` `.bmp` `.avif` `.ico` |
| PDF | `.pdf` |
| Audio | `.mp3` `.wav` `.ogg` `.oga` `.m4a` `.flac` `.aac` |
| Video | `.mp4` `.webm` `.ogv` `.mov` |
| Table | `.csv` `.tsv` |
| Markdown | `.md` `.markdown` |
| Source | ~40 suffixes (`.py` `.js` `.ts` `.json` `.yaml` `.toml` `.sql` `.go` `.rs` …) plus suffixless `Dockerfile`, `Makefile`, `Gemfile`, `Rakefile`, `justfile`, `LICENSE`, `NOTICE`, `AUTHORS`, `README` and `changelog` |

Anything else offers a download. Set `sniff_text=True` to additionally preview
unrecognised files whose first 8 KiB decode as UTF-8 and contain no NUL bytes.

`.svg` and `.html` are shown **as source**, not rendered — see below.

The tables are plain module-level dicts, so you can extend them:

```python
from nicegui_treebrowser import filetypes

filetypes.CODE_LANGUAGES[".ino"] = "cpp"
filetypes.IMAGE_SUFFIXES.add(".jxl")
```

## Security

Read this before pointing the widget at anything sensitive.

- **`root` is the boundary.** Tree keys are resolved back through a dictionary built
  by walking `root`, and the result is re-checked against `root` before anything is
  served. A key naming a path outside the root, or one that was never in the tree,
  resolves to nothing.
- **Symlinks are skipped entirely**, so a link inside the root cannot be used to read
  or traverse outside it.
- **`exclude` and `show_hidden` are real filters**, not just display ones. A file they
  keep out of the tree cannot be previewed or downloaded.
- **Previewing a file publishes it at an app URL** for as long as the preview is on
  screen, and downloading publishes it briefly. Those URLs are unguessable in
  practice but carry no authentication of their own — whatever middleware protects
  your NiceGUI app protects them too, and nothing else does. If your app is public,
  so is anything in `root`.
- **`.svg` and `.html` are deliberately shown as source.** Both are served from your
  app's own origin, so rendering them would run any script they carry with your
  app's cookies in scope.

## License

MIT
