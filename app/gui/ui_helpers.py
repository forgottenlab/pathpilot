from __future__ import annotations

import os
from pathlib import Path

from app.core.json_store import atomic_write_json, read_json


def open_in_explorer(path_str: str) -> None:
    path = Path(path_str)
    if path.exists():
        os.startfile(str(path))
    else:
        parent = path.parent
        if parent.exists():
            os.startfile(str(parent))


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
