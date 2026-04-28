from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.core.paths import get_pending_installs_path, ensure_user_config_files


def _ensure_queue_file() -> None:
    ensure_user_config_files()
    path = get_pending_installs_path()

    if not path.exists():
        with path.open("w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def load_pending_installs() -> list[dict[str, Any]]:
    _ensure_queue_file()
    path = get_pending_installs_path()

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    return data


def save_pending_installs(items: list[dict[str, Any]]) -> None:
    _ensure_queue_file()
    path = get_pending_installs_path()

    with path.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _next_id(items: list[dict[str, Any]]) -> int:
    if not items:
        return 1
    return max(int(item.get("id", 0)) for item in items) + 1


def add_install_suggestion(suggestion: dict[str, Any]) -> dict[str, Any]:
    items = load_pending_installs()

    installer_path = suggestion["installer"]
    for item in items:
        if item.get("installer") == installer_path and item.get("status") == "pending":
            return item

    record = {
        "id": _next_id(items),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "pending",
        **suggestion,
    }

    items.append(record)
    save_pending_installs(items)
    return record


def update_install_suggestion_status(record_id: int, status: str) -> dict[str, Any] | None:
    items = load_pending_installs()

    for item in items:
        if int(item.get("id", 0)) == int(record_id):
            item["status"] = status
            item["updated_at"] = datetime.now().isoformat(timespec="seconds")
            save_pending_installs(items)
            return item

    return None


def get_pending_items() -> list[dict[str, Any]]:
    return [
        item for item in load_pending_installs()
        if item.get("status") == "pending"
    ]
