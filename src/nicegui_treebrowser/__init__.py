"""A NiceGUI element for browsing, previewing and downloading a
server-side directory."""

from importlib.metadata import PackageNotFoundError, version

from .browser import TreeBrowser

__all__ = ["TreeBrowser", "__version__"]

try:
    __version__ = version("nicegui-treebrowser")
except PackageNotFoundError:  # pragma: no cover - running from a source tree
    __version__ = "0.0.0.dev0"
