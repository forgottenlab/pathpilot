from __future__ import annotations

import os
from pathlib import Path

from app.core.json_store import atomic_write_json, read_json


def open_directory_in_explorer(path_str: str | Path) -> bool:
    """Open an existing directory only; invalid paths and OS failures are no-ops."""
    if not isinstance(path_str, (str, Path)) or not str(path_str).strip():
        return False
    try:
        directory = Path(path_str).resolve(strict=True)
        if not directory.is_dir():
            return False
        # Never use the default file association, even for a directory action.
        os.startfile(str(directory), "explore")
        return True
    except (OSError, ValueError, RuntimeError):
        return False


def reveal_file_in_explorer(path_str: str | Path) -> bool:
    """Open the containing directory, never the file (which may be missing)."""
    if not isinstance(path_str, (str, Path)) or not str(path_str).strip():
        return False
    try:
        # Do not resolve the file itself: a link should reveal its own location.
        path = Path(path_str)
        if "\x00" in str(path):
            return False
        return open_directory_in_explorer(path.absolute().parent)
    except (OSError, ValueError, RuntimeError):
        return False


def normalize_display_name(name: str) -> str:
    """
    proofing (1) -> proofing
    仅用于显示，不改真实文件名。
    """
    if name.endswith(")"):
        left = name.rfind(" (")
        if left != -1:
            tail = name[left + 2:-1]
            if tail.isdigit():
                return name[:left]
    return name


def load_json_file(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    return read_json(path, expected_type=dict)


def save_json_file(path: str | Path, data: dict) -> None:
    atomic_write_json(path, data)
