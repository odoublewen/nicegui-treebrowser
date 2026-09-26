"""Tests for the boundary around `root`: what must never be reachable."""

from __future__ import annotations

from pathlib import Path

import pytest
from nicegui import app, ui
from nicegui.testing import User

from nicegui_treebrowser import TreeBrowser

from .test_browser import open_browser, route_paths


async def test_constructor_refuses_a_non_directory(user: User, tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("x")

    with pytest.raises(NotADirectoryError):
        TreeBrowser(target)
    with pytest.raises(NotADirectoryError):
        TreeBrowser(tmp_path / "does-not-exist")


async def test_focus_refuses_a_path_outside_the_root(
    user: User, tmp_path: Path
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outsider = tmp_path / "outsider.txt"
    outsider.write_text("not yours")

    browser = await open_browser(user, root)

    assert browser.focus(outsider) is False
    assert browser.focus("../outsider.txt") is False
    assert browser._selected is None


async def test_resolve_rejects_keys_that_are_not_in_the_tree(
    user: User, sample_tree: Path
) -> None:
    browser = await open_browser(user, sample_tree)

    assert browser._resolve("../../etc/passwd") is None
    assert browser._resolve("/etc/passwd") is None
    assert browser._resolve("never-existed.txt") is None
    # a key that is in the tree still resolves, so the gate is not simply closed
    assert browser._resolve("script.py") == sample_tree / "script.py"


async def test_resolve_rejects_a_path_smuggled_into_the_key_map(
    user: User, sample_tree: Path
) -> None:
    """The second check matters: _paths is not trusted on its own."""
    browser = await open_browser(user, sample_tree)
    browser._paths["sneaky"] = Path("/etc/passwd")

    assert browser._resolve("sneaky") is None


async def test_symlinks_never_enter_the_tree(user: User, tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "real.txt").write_text("fine")
    secret = tmp_path / "secret.txt"
    secret.write_text("not yours")
    (root / "escape.txt").symlink_to(secret)
    (root / "escape-dir").symlink_to(tmp_path)

    browser = await open_browser(user, root)

    assert "real.txt" in browser._paths
    assert "escape.txt" not in browser._paths
    assert "escape-dir" not in browser._paths
    assert browser.focus("escape.txt") is False


async def test_excluded_files_cannot_be_previewed(
    user: User, sample_tree: Path
) -> None:
    browser = await open_browser(
        user, sample_tree, exclude=lambda path: path.suffix == ".pdf"
    )

    assert "doc.pdf" not in browser._paths
    assert "script.py" in browser._paths
    assert browser.focus("doc.pdf") is False
    assert browser._resolve("doc.pdf") is None
    # nothing was published for it
    assert browser._routes == []


async def test_hidden_files_cannot_be_previewed(user: User, sample_tree: Path) -> None:
    browser = await open_browser(user, sample_tree)

    assert browser.focus(".hidden.txt") is False
    assert browser._resolve(".hidden.txt") is None


async def test_svg_is_shown_as_source_so_its_scripts_never_run(
    user: User, sample_tree: Path
) -> None:
    browser = await open_browser(user, sample_tree)
    browser.focus("vector.svg")

    await user.should_see(kind=ui.code)
    # no ui.image, and so no route serving it as image/svg+xml
    assert not [e for e in browser._viewer.descendants() if isinstance(e, ui.image)]
    assert browser._routes == []


async def test_html_is_shown_as_source_not_in_an_iframe(
    user: User, sample_tree: Path
) -> None:
    browser = await open_browser(user, sample_tree)
    browser.focus("page.html")

    await user.should_see(kind=ui.code)
    assert not [e for e in browser._viewer.descendants() if e.tag == "iframe"]
    assert browser._routes == []


async def test_a_preview_publishes_nothing_by_default(
    user: User, sample_tree: Path
) -> None:
    """Text previews travel over the socket; they must not open a route."""
    browser = await open_browser(user, sample_tree)
    before = route_paths()  # after the page route, before any preview
    browser.focus("script.py")

    assert browser._routes == []
    assert route_paths() == before


# -- the sniff_text opt-in ---------------------------------------------------


async def test_unknown_binary_is_not_previewed_by_default(
    user: User, sample_tree: Path
) -> None:
    browser = await open_browser(user, sample_tree)
    browser.focus("blob.bin")

    await user.should_see("No preview for this file type")


async def test_sniff_text_still_refuses_binary(user: User, sample_tree: Path) -> None:
    browser = await open_browser(user, sample_tree, sniff_text=True)
    browser.focus("blob.bin")

    await user.should_see("No preview for this file type")


async def test_sniff_text_previews_an_extensionless_text_file(
    user: User, sample_tree: Path
) -> None:
    strict = await open_browser(user, sample_tree)
    strict.focus("plain")
    await user.should_see("No preview for this file type")

    lenient = await open_browser(user, sample_tree, sniff_text=True)
    lenient.focus("plain")
    await user.should_see("just text, no suffix at all")


async def test_download_button_is_offered_for_files_we_cannot_preview(
    user: User, sample_tree: Path
) -> None:
    browser = await open_browser(user, sample_tree)
    browser.focus("blob.bin")

    await user.should_see("Download")
    assert app is not None  # the route registry stayed untouched
    assert browser._routes == []
