"""The :class:`TreeBrowser` NiceGUI element."""

from __future__ import annotations

import csv
import logging
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from nicegui import app, events, ui

from . import filetypes
from .fsutil import get_dir_size, looks_like_text, make_tarball, natural_size, read_text

LOG = logging.getLogger(__name__)

__all__ = ["TreeBrowser"]


# inspired by (but not copied from)
# https://github.com/zauberzeug/nicegui/tree/main/examples/local_file_picker
class TreeBrowser(ui.column):
    """Browse, preview and download the contents of a server-side directory.

    A NiceGUI element: it renders where it is created, and takes `.classes()`,
    `.style()`, `.props()` and `.move()` like any other `ui.*` element.

    :param root: directory to expose; nothing outside it is ever served
    :param focus: file or folder to reveal and open upon init
    :param title: heading shown above the tree
    :param show_hidden: include dot-files and dot-directories
    :param exclude: predicate function returning True for paths to exclude
    :param max_preview_bytes: largest text preview to load into the browser
    :param max_table_rows: row cap for .csv/.tsv previews
    :param allow_archive: show the "Download all" and per-folder archive buttons
    :param show_full_path: show the full path of the directory
    :param sniff_text: preview unrecognised files that look like UTF-8 text,
        instead of offering only a download
    """

    _tree_container: ui.column
    _tree: ui.tree
    _viewer: ui.column

    def __init__(
        self,
        root: str | Path,
        *,
        focus: str | Path | None = None,
        title: str = "Files",
        show_hidden: bool = False,
        exclude: Callable[[Path], bool] | None = None,
        max_preview_bytes: int = 1000000,
        max_table_rows: int = 5000,
        allow_archive: bool = True,
        show_full_path: bool = True,
        sniff_text: bool = False,
    ) -> None:
        resolved_root = Path(root).expanduser().resolve()
        if not resolved_root.is_dir():
            raise NotADirectoryError(f"{resolved_root} is not a directory")

        super().__init__()
        self.root = resolved_root
        self.title = title
        self.show_hidden = show_hidden
        self.exclude = exclude
        self.max_preview_bytes = max_preview_bytes
        self.max_table_rows = max_table_rows
        self.allow_archive = allow_archive
        self.show_full_path = show_full_path
        self.sniff_text = sniff_text

        self._paths: dict[str, Path] = {}
        self._selected: str | None = None
        # URLs this browser has published for the current preview; see _pane()
        self._routes: list[str] = []

        self.classes("w-full min-h-[50vh] gap-0 p-0 flex-nowrap")
        with self:
            self._build_header()
            with ui.splitter(value=32).classes("w-full min-h-0 flex-grow") as splitter:
                with splitter.before:
                    self._build_sidebar()
                with splitter.after:
                    self._viewer = ui.column().classes(
                        "w-full h-full gap-4 p-6 overflow-auto flex-nowrap"
                    )
            if focus is None or not self.focus(focus):
                self._show_placeholder()

    def focus(self, path: str | Path, *, collapse_others: bool = True) -> bool:
        """Select path and open just the folders needed to reveal it.

        Only the target's ancestors are expanded — an expanded sibling branch is
        never needed to show it. The target itself stays as it is, so focusing a
        folder reveals it without dumping its contents into the tree.

        Accepts an absolute path or one relative to the root. Returns False if
        the path lies outside the root or is not in the tree (missing, hidden,
        or excluded), in which case the current selection is left alone. To
        open the browser on a given path, pass `focus=` to the constructor.

        :param path: the file or folder to reveal
        :param collapse_others: close every other branch, so only this one is open
        """

        target = Path(path).expanduser()
        if not target.is_absolute():
            target = self.root / target
        target = target.resolve()
        try:
            key = self._key(target)
        except ValueError:
            ui.notify(f"{target} is outside {self.root}", type="warning")
            return False

        if key not in self._paths:
            self.refresh()  # the tree may predate the file
        if key not in self._paths:
            ui.notify(f"{target.name} is not in this tree", type="warning")
            return False

        if collapse_others:
            self._tree.collapse()
        ancestors = self._ancestor_keys(target)
        if ancestors:
            self._tree.expand(ancestors)
        self._tree.select(key)
        self._selected = key

        self._display(target)
        self._scroll_to_selection()
        return True

    def refresh(self) -> None:
        """Re-read the directory tree from disk and redraw it."""
        self._tree_container.clear()
        with self._tree_container:
            self._build_tree()
        if self._selected is not None and self._selected not in self._paths:
            self._selected = None
            self._show_placeholder()

    def _build_header(self) -> None:
        with ui.row().classes(
            "w-full items-center justify-between gap-4 px-6 py-3 "
            "border-b border-gray-200 dark:border-gray-700"
        ):
            with ui.column().classes("gap-0 min-w-0"):
                ui.label(self.title).classes("text-lg font-medium leading-tight")
                if self.show_full_path:
                    ui.label(str(self.root)).classes(
                        "text-xs text-gray-500 font-mono truncate"
                    )
            with ui.row().classes("items-center gap-2 flex-nowrap"):
                ui.button(icon="refresh", on_click=self.refresh).props(
                    "flat round dense"
                ).tooltip("Reload the tree from disk")
                if self.allow_archive:
                    ui.button(
                        "Download all",
                        icon="archive",
                        on_click=lambda: self._download_archive(self.root),
                    ).props("outline no-caps")

    def _build_sidebar(self) -> None:
        with ui.column().classes("w-full h-full gap-0 flex-nowrap"):
            search = (
                ui.input(placeholder="Filter by name")
                .props("dense outlined clearable")
                .classes("w-full px-3 py-2")
            )
            search.on_value_change(lambda e: self._filter(e.value))
            self._tree_container = ui.column().classes(
                "w-full min-h-0 flex-grow overflow-auto px-2 pb-4 flex-nowrap"
            )
            with self._tree_container:
                self._build_tree()

    def _build_tree(self) -> None:
        self._paths.clear()
        self._tree = ui.tree(
            [self._node(self.root)],
            label_key="label",
            on_select=self._on_select,
        ).classes("w-full")
        self._tree.expand()

    def _node(self, path: Path) -> dict[str, Any]:
        key = self._key(path)
        self._paths[key] = path
        node: dict[str, Any] = {
            "id": key,
            "label": path.name or str(path),
            "icon": "folder" if path.is_dir() else filetypes.icon_for(path),
        }
        if path.is_dir():
            node["children"] = [self._node(child) for child in self._entries(path)]
        return node

    def _entries(self, directory: Path) -> Iterable[Path]:
        try:
            entries = list(directory.iterdir())
        except PermissionError:
            return []
        entries = [entry for entry in entries if not self._skip(entry)]
        # directories first, then files, each alphabetically and case-insensitively
        entries.sort(key=lambda entry: (not entry.is_dir(), entry.name.lower()))
        return entries

    def _skip(self, path: Path) -> bool:
        if not self.show_hidden and path.name.startswith("."):
            return True
        if path.is_symlink():  # keeps the walk free of loops and escapes
            return True
        if not path.is_dir() and not path.is_file():
            return True
        return bool(self.exclude and self.exclude(path))

    def _key(self, path: Path) -> str:
        relative = path.relative_to(self.root).as_posix()
        return relative or "."

    def _ancestor_keys(self, path: Path) -> list[str]:
        """Keys of every folder between the root and *path*, outermost first."""
        keys: list[str] = []
        current = path
        while current != self.root:
            current = current.parent
            keys.append(self._key(current))
        keys.reverse()
        return keys

    def _resolve(self, key: str) -> Path | None:
        """Map a tree key back to a path, refusing anything outside the root."""
        path = self._paths.get(key)
        if path is None:
            return None
        resolved = path.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            return None
        return resolved if resolved.exists() else None

    def _filter(self, text: str | None) -> None:
        # QTree's own filter prop: matching nodes stay, the rest are hidden.
        self._tree.filter = text or ""

    # -- selection ---------------------------------------------------------

    # ValueChangeEventArguments only became generic in NiceGUI 3.0; the
    # subscript is safe on 2.x because `from __future__ import annotations`
    # keeps it an unevaluated string.
    def _on_select(self, event: events.ValueChangeEventArguments[str | None]) -> None:
        key = event.value
        self._selected = key
        if key is None:
            self._show_placeholder()
            return
        path = self._resolve(key)
        if path is None:
            self._show_message(
                "That item is gone", "Reload the tree to see what changed."
            )
            return
        self._display(path)

    def _display(self, path: Path) -> None:
        if path.is_dir():
            self._show_directory(path)
        else:
            self._show_file(path)

    def _scroll_to_selection(self) -> None:
        with self._tree_container:
            ui.timer(0.1, self._scroll_now, once=True)

    def _scroll_now(self) -> None:
        try:
            ui.run_javascript(f"""
                getElement({self._tree.id})?.$el
                    ?.querySelector(
                        '.q-tree__node--selected, .q-tree__node-header--selected')
                    ?.scrollIntoView({{block: 'nearest'}});
            """)
        except Exception as e:
            # the client went away; the scroll is cosmetic either way
            LOG.warning(e)

    def _pane(self) -> ui.element:
        # Elements that publish their own file (ui.image, ui.audio, ui.video)
        # drop their route when they are deleted. The PDF iframe has no such
        # element behind it, so retire those routes here: a file stays reachable
        # only for as long as the preview that published it is on screen.
        for url in self._routes:
            app.remove_route(url)
        self._routes.clear()
        self._viewer.clear()
        return self._viewer

    def _show_placeholder(self) -> None:
        with (
            self._pane(),
            ui.column().classes("w-full h-full items-center justify-center gap-2"),
        ):
            ui.icon("folder_open", size="3rem").classes("text-gray-400")
            ui.label("Pick a file to read it here.").classes("text-gray-500")

    def _show_message(self, heading: str, detail: str) -> None:
        with self._pane():
            ui.label(heading).classes("text-lg font-medium")
            ui.label(detail).classes("text-gray-500")

    def _show_directory(self, path: Path) -> None:
        with self._pane():
            # _resolve() has already confirmed the path, but it may still go
            # away between that check and this read.
            try:
                files, directories, total = get_dir_size(path)
                self._file_header(path)
            except OSError as error:
                ui.label(f"Could not read this folder: {error}").classes("text-red-600")
                return
            ui.label(
                f"{files} file{'' if files == 1 else 's'} in "
                f"{directories} subfolder{'' if directories == 1 else 's'} · "
                f"{natural_size(total)}"
            ).classes("text-sm text-gray-500")

    def _show_file(self, path: Path) -> None:
        kind = filetypes.classify(path)
        with self._pane():
            # The header stats the file, so it belongs inside the guard too: the
            # file may vanish between _resolve() confirming it and this read.
            try:
                self._file_header(path)
                self._preview(path, kind)
            except Exception as error:  # unreadable file, bad CSV, broken encoding…
                ui.label(f"Could not read this file: {error}").classes("text-red-600")

    def _preview(self, path: Path, kind: filetypes.PreviewKind) -> None:
        if kind == "image":
            self._preview_image(path)
        elif kind == "pdf":
            self._preview_pdf(path)
        elif kind == "audio":
            self._preview_audio(path)
        elif kind == "video":
            self._preview_video(path)
        elif kind == "table":
            self._preview_table(path, filetypes.table_delimiter(path))
        elif kind == "markdown":
            self._preview_markdown(path)
        elif kind == "code":
            self._preview_code(path, filetypes.code_language(path))
        elif self.sniff_text and looks_like_text(path):
            self._preview_code(path, "text")
        else:
            ui.label(
                "No preview for this file type — download it to open it locally."
            ).classes("text-gray-500")

    def _file_header(self, path: Path) -> None:
        info = path.stat()
        with ui.row().classes("w-full items-start justify-between gap-4 flex-nowrap"):
            with ui.column().classes("gap-1 min-w-0"):
                ui.label(path.name or str(path)).classes("text-lg font-medium truncate")
                details = [
                    datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d %H:%M")
                ]
                if path.is_file():
                    details.insert(0, natural_size(info.st_size))
                ui.label(" · ".join(details)).classes("text-xs text-gray-500")
            with ui.row().classes("items-center gap-2 flex-nowrap"):
                if path.is_file():
                    ui.button(
                        "Download",
                        icon="download",
                        on_click=lambda p=path: ui.download.file(p, p.name),
                    ).props("outline no-caps")
                elif self.allow_archive:
                    ui.button(
                        "Download folder",
                        icon="archive",
                        on_click=lambda p=path: self._download_archive(p),
                    ).props("outline no-caps")

    def _preview_code(self, path: Path, language: str) -> None:
        text, truncated = read_text(path, self.max_preview_bytes)
        if truncated:
            self._truncation_note(
                f"Showing the first {natural_size(self.max_preview_bytes)}."
            )
        ui.code(text, language=language).classes("w-full")

    def _preview_markdown(self, path: Path) -> None:
        text, truncated = read_text(path, self.max_preview_bytes)
        if truncated:
            self._truncation_note(
                f"Showing the first {natural_size(self.max_preview_bytes)}."
            )
        ui.markdown(text).classes("w-full max-w-none prose dark:prose-invert")

    def _preview_image(self, path: Path) -> None:
        # ui.image publishes the file itself and retires the route when the
        # element is deleted, so there is nothing for us to clean up.
        ui.image(path).classes("max-w-full").style("max-height: 80vh")

    def _preview_audio(self, path: Path) -> None:
        ui.audio(path).classes("w-full")

    def _preview_video(self, path: Path) -> None:
        # ui.video serves through add_media_file, which honours Range requests,
        # so the viewer can seek without downloading the whole file first.
        ui.video(path).classes("w-full").style("max-height: 80vh")

    def _preview_pdf(self, path: Path) -> None:
        url = app.add_static_file(local_file=path)
        self._routes.append(url)
        ui.element("iframe").props(f'src="{url}"').classes(
            "w-full min-h-[70vh] flex-grow border-0"
        )

    def _preview_table(self, path: Path, delimiter: str) -> None:
        with open(path, newline="", encoding="utf-8", errors="replace") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            header = next(reader, None)
            if header is None:
                ui.label("This file is empty.").classes("text-gray-500")
                return
            # Synthetic field names: a CSV header may repeat itself, be blank,
            # or collide with the row key, none of which QTable tolerates.
            fields = [f"c{index}" for index in range(len(header))]
            rows: list[dict[str, Any]] = []
            truncated = False
            for index, record in enumerate(reader):
                if index >= self.max_table_rows:
                    truncated = True
                    break
                row: dict[str, Any] = dict(zip(fields, record, strict=False))
                row["_row"] = index
                rows.append(row)
        if truncated:
            self._truncation_note(f"Showing the first {self.max_table_rows:,} rows.")
        columns = [
            {
                "name": field,
                "label": label,
                "field": field,
                "align": "left",
                "sortable": True,
            }
            for field, label in zip(fields, header, strict=True)
        ]
        ui.table(rows=rows, columns=columns, row_key="_row", pagination=25).classes(
            "w-full"
        )

    @staticmethod
    def _truncation_note(text: str) -> None:
        with ui.row().classes("items-center gap-2 text-xs text-gray-500"):
            ui.icon("content_cut", size="1rem")
            ui.label(f"{text} Download the file for everything.")

    def _download_archive(self, path: Path) -> None:
        name = path.name or self.root.name or "archive"
        try:
            data = make_tarball(str(path), name)
        except Exception as error:
            ui.notify(f"Could not pack {name}.tar.gz: {error}", type="negative")
            return
        ui.download.content(data, f"{name}.tar.gz", media_type="application/gzip")
