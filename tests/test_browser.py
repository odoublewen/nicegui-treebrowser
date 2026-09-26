"""Integration tests driving TreeBrowser through NiceGUI's simulated user."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
from nicegui import app, ui
from nicegui.testing import User

from nicegui_treebrowser import TreeBrowser


async def open_browser(user: User, root: Path, **kwargs: Any) -> TreeBrowser:
    """Serve a TreeBrowser at "/", open it, and hand back the element."""
    holder: list[TreeBrowser] = []

    @ui.page("/")
    def page() -> None:
        holder.append(TreeBrowser(root, **kwargs))

    await user.open("/")
    assert len(holder) == 1
    return holder[0]


def route_paths() -> list[str]:
    return [getattr(route, "path", "") for route in app.routes]


def only[T: ui.element](browser: TreeBrowser, kind: type[T]) -> T:
    """Return the single element of type *kind* in the preview pane."""
    found = [e for e in browser._viewer.descendants() if isinstance(e, kind)]
    assert len(found) == 1, f"expected one {kind.__name__}, found {len(found)}"
    return found[0]


# -- the tree ----------------------------------------------------------------


async def test_tree_lists_visible_entries(user: User, sample_tree: Path) -> None:
    await open_browser(user, sample_tree, title="Results")

    await user.should_see("Results")
    await user.should_see(kind=ui.tree)
    await user.should_see("Pick a file to read it here.")


async def test_hidden_files_stay_out_of_the_tree(user: User, sample_tree: Path) -> None:
    browser = await open_browser(user, sample_tree)
    assert ".hidden.txt" not in browser._paths

    shown = await open_browser(user, sample_tree, show_hidden=True)
    assert ".hidden.txt" in shown._paths


async def test_full_path_is_shown_under_the_title_by_default(
    user: User, sample_tree: Path
) -> None:
    await open_browser(user, sample_tree, title="Results")

    await user.should_see("Results")
    await user.should_see(str(sample_tree))


async def test_show_full_path_false_hides_it(user: User, sample_tree: Path) -> None:
    await open_browser(user, sample_tree, title="Results", show_full_path=False)

    await user.should_see("Results")
    await user.should_not_see(str(sample_tree))


async def test_filter_sets_the_quasar_filter_prop(
    user: User, sample_tree: Path
) -> None:
    browser = await open_browser(user, sample_tree)

    browser._filter("scri")
    assert browser._tree.filter == "scri"
    assert browser._tree.props["filter"] == "scri"

    browser._filter(None)
    assert browser._tree.filter == ""


async def test_refresh_picks_up_a_new_file(user: User, sample_tree: Path) -> None:
    browser = await open_browser(user, sample_tree)
    assert "added.py" not in browser._paths

    (sample_tree / "added.py").write_text("x = 1\n")
    browser.refresh()

    assert "added.py" in browser._paths


async def test_focus_expands_only_ancestors(user: User, sample_tree: Path) -> None:
    browser = await open_browser(user, sample_tree)

    assert browser.focus("logs/run.log") is True
    assert browser._selected == "logs/run.log"
    assert set(browser._tree.props["expanded"]) == {".", "logs"}
    await user.should_see("run.log")


async def test_focus_argument_opens_the_browser_on_a_file(
    user: User, sample_tree: Path
) -> None:
    await open_browser(user, sample_tree, focus="script.py")

    await user.should_see("hello from script")
    await user.should_not_see("Pick a file to read it here.")


# -- previews ----------------------------------------------------------------


async def test_code_preview_shows_file_contents(user: User, sample_tree: Path) -> None:
    browser = await open_browser(user, sample_tree)
    browser.focus("script.py")

    await user.should_see(kind=ui.code)
    await user.should_see("hello from script")


async def test_markdown_preview(user: User, sample_tree: Path) -> None:
    browser = await open_browser(user, sample_tree)
    browser.focus("README.md")

    await user.should_see(kind=ui.markdown)
    await user.should_see("Some *markdown*.")


async def test_image_preview_publishes_the_file(user: User, sample_tree: Path) -> None:
    browser = await open_browser(user, sample_tree)
    browser.focus("picture.png")

    await user.should_see(kind=ui.image)
    image = only(browser, ui.image)
    # ui.image publishes the file itself and serves it from that route
    assert image.props["src"] in route_paths()
    response = await user.http_client.get(image.props["src"])
    assert response.status_code == 200
    assert response.content == (sample_tree / "picture.png").read_bytes()


async def test_pdf_preview_renders_an_iframe_over_a_live_route(
    user: User, sample_tree: Path
) -> None:
    browser = await open_browser(user, sample_tree)
    browser.focus("doc.pdf")

    assert len(browser._routes) == 1
    url = browser._routes[0]
    assert url in route_paths()

    response = await user.http_client.get(url)
    assert response.status_code == 200
    assert response.content == (sample_tree / "doc.pdf").read_bytes()

    iframes = [e for e in browser._viewer.descendants() if e.tag == "iframe"]
    assert len(iframes) == 1
    assert iframes[0].props["src"] == url


async def test_pdf_route_is_retired_when_the_preview_goes_away(
    user: User, sample_tree: Path, caplog: pytest.LogCaptureFixture
) -> None:
    browser = await open_browser(user, sample_tree)
    browser.focus("doc.pdf")
    url = browser._routes[0]
    assert url in route_paths()

    browser.focus("script.py")

    assert browser._routes == []
    assert url not in route_paths()
    # NiceGUI logs a warning for the 404 we are deliberately provoking, and the
    # `user` fixture fails a test that leaves unexpected logs behind.
    with caplog.at_level(logging.ERROR, logger="nicegui"):
        assert (await user.http_client.get(url)).status_code == 404


async def test_audio_and_video_previews(user: User, sample_tree: Path) -> None:
    browser = await open_browser(user, sample_tree)

    browser.focus("song.mp3")
    await user.should_see(kind=ui.audio)

    browser.focus("clip.mp4")
    await user.should_see(kind=ui.video)


async def test_table_preview_uses_the_csv_header_as_labels(
    user: User, sample_tree: Path
) -> None:
    browser = await open_browser(user, sample_tree)
    browser.focus("data.csv")

    await user.should_see(kind=ui.table)
    table = only(browser, ui.table)
    assert [column["label"] for column in table.columns] == ["name", "score"]
    assert table.rows == [
        {"c0": "ada", "c1": "42", "_row": 0},
        {"c0": "grace", "c1": "99", "_row": 1},
    ]


async def test_table_preview_honours_the_tsv_delimiter(
    user: User, sample_tree: Path
) -> None:
    browser = await open_browser(user, sample_tree)
    browser.focus("table.tsv")

    table = only(browser, ui.table)
    assert [column["label"] for column in table.columns] == ["a", "b"]
    assert table.rows == [{"c0": "1", "c1": "2", "_row": 0}]


async def test_table_preview_caps_rows_and_says_so(user: User, tmp_path: Path) -> None:
    target = tmp_path / "big.csv"
    target.write_text("n\n" + "".join(f"{i}\n" for i in range(50)))

    browser = await open_browser(user, tmp_path, max_table_rows=10)
    browser.focus("big.csv")

    table = only(browser, ui.table)
    assert len(table.rows) == 10
    await user.should_see("Showing the first 10 rows.")


async def test_table_preview_tolerates_duplicate_and_ragged_columns(
    user: User, tmp_path: Path
) -> None:
    (tmp_path / "odd.csv").write_text("id,id,\n1,2\n3,4,5\n")

    browser = await open_browser(user, tmp_path)
    browser.focus("odd.csv")

    table = only(browser, ui.table)
    assert [column["name"] for column in table.columns] == ["c0", "c1", "c2"]
    assert table.rows[0] == {"c0": "1", "c1": "2", "_row": 0}


async def test_empty_table_says_so_instead_of_raising(
    user: User, tmp_path: Path
) -> None:
    (tmp_path / "empty.csv").write_text("")

    browser = await open_browser(user, tmp_path)
    browser.focus("empty.csv")

    await user.should_see("This file is empty.")


async def test_code_preview_reports_truncation(user: User, tmp_path: Path) -> None:
    (tmp_path / "long.py").write_text("# " + "x" * 5000 + "\n")

    browser = await open_browser(user, tmp_path, max_preview_bytes=100)
    browser.focus("long.py")

    await user.should_see("Showing the first 100 bytes.")


async def test_directory_preview_reports_its_contents(
    user: User, sample_tree: Path
) -> None:
    browser = await open_browser(user, sample_tree)
    browser.focus("logs")

    await user.should_see("1 file in 0 subfolders")


async def test_unreadable_file_reports_the_error_instead_of_crashing(
    user: User, tmp_path: Path
) -> None:
    target = tmp_path / "gone.py"
    target.write_text("x = 1\n")

    browser = await open_browser(user, tmp_path)
    target.unlink()
    browser._show_file(target)

    await user.should_see("Could not read this file")


# -- serving ------------------------------------------------------------------


async def test_video_route_honours_range_requests(
    user: User, sample_tree: Path
) -> None:
    """Seeking in the player depends on partial responses, so assert on them."""
    browser = await open_browser(user, sample_tree)
    browser.focus("clip.mp4")

    video = only(browser, ui.video)
    whole = (sample_tree / "clip.mp4").read_bytes()

    response = await user.http_client.get(
        video.props["src"], headers={"Range": "bytes=4-11"}
    )
    assert response.status_code == 206
    assert response.headers["content-range"] == f"bytes 4-11/{len(whole)}"
    assert response.content == whole[4:12]


async def test_image_route_disappears_when_the_preview_is_replaced(
    user: User, sample_tree: Path
) -> None:
    browser = await open_browser(user, sample_tree)
    browser.focus("picture.png")
    url = only(browser, ui.image).props["src"]
    assert url in route_paths()

    browser.focus("script.py")

    assert url not in route_paths()


async def test_download_button_requests_the_selected_file(
    user: User, sample_tree: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # allow_archive=False so "Download" is unambiguous: no "Download all" button
    browser = await open_browser(user, sample_tree, allow_archive=False)
    browser.focus("script.py")

    # NiceGUI's download simulation fetches the local path as though it were a
    # URL, so the response is a 404 and only the request tells us anything.
    with caplog.at_level(logging.ERROR, logger="nicegui"):
        user.find("Download").click()
        response = await user.download.next()

    assert response.request.url.path == str(sample_tree / "script.py")


async def test_download_all_sends_a_tarball_of_the_root(
    user: User, sample_tree: Path
) -> None:
    import io
    import tarfile

    await open_browser(user, sample_tree)

    user.find("Download all").click()
    response = await user.download.next()

    with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as archive:
        assert "sample/script.py" in archive.getnames()


async def test_folder_download_sends_a_tarball_of_that_folder(
    user: User, sample_tree: Path
) -> None:
    import io
    import tarfile

    browser = await open_browser(user, sample_tree)
    browser.focus("logs")

    user.find("Download folder").click()
    response = await user.download.next()

    with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as archive:
        assert archive.getnames() == ["logs", "logs/run.log"]


async def test_archive_buttons_are_hidden_when_not_allowed(
    user: User, sample_tree: Path
) -> None:
    browser = await open_browser(user, sample_tree, allow_archive=False)

    await user.should_not_see("Download all")
    browser.focus("logs")
    await user.should_not_see("Download folder")
