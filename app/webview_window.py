from __future__ import annotations

import sys
from pathlib import Path

from app.installer import APP_DIR

WEBVIEW_DATA_DIR = APP_DIR / "webview"


def open_window(title: str, url: str, profile_slug: str) -> None:
    """Open a native webview window for a Core Utils web section.

    Web sections use the same persistent storage profile so cookies and
    OAuth sessions, including GitHub sign-in, are shared across them.
    """
    import webview

    storage_path = WEBVIEW_DATA_DIR / profile_slug
    storage_path.mkdir(parents=True, exist_ok=True)

    webview.create_window(title, url, width=1180, height=820, min_size=(720, 560))
    webview.start(private_mode=False, storage_path=str(storage_path))


def main() -> None:
    if len(sys.argv) != 4:
        print("usage: python -m app.webview_window <title> <url> <profile_slug>", file=sys.stderr)
        raise SystemExit(2)
    _, title, url, profile_slug = sys.argv
    open_window(title, url, profile_slug)


if __name__ == "__main__":
    main()
