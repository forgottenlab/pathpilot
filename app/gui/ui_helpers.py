from __future__ import annotations

import json
import os
from pathlib import Path


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
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(path: str | Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
