"""Filesystem locations of bundled application assets."""

from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ICON_PATH = ASSETS_DIR / "Icon.png"
