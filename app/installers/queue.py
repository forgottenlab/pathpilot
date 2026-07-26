from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.core.paths import get_pending_installs_path, ensure_user_config_files


STRUCTURED_EXECUTION_FIELDS = {
    "executable",
    "args",
    "preview",
    "installer_path",
    "target_dir",
    "installer_family",
    "mode",
}


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

    normalized: list[dict[str, Any]] = []
    changed = False
    for item in data:
        if not isinstance(item, dict):
            changed = True
            continue
        record = dict(item)
        has_structured_execution = (
            STRUCTURED_EXECUTION_FIELDS.issubset(record)
            and isinstance(record.get("executable"), str)
            and isinstance(record.get("args"), list)
            and all(isinstance(arg, str) for arg in record.get("args", []))
        )
        if not has_structured_execution and "command" in record:
            if record.get("status") != "legacy_unsafe":
                record["status"] = "legacy_unsafe"
                record["updated_at"] = datetime.now().isoformat(timespec="seconds")
                changed = True
            if "legacy_preview" not in record:
                record["legacy_preview"] = str(record.get("command", ""))
                changed = True
            if "legacy_reason" not in record:
                record["legacy_reason"] = (
                    "Command-only records cannot be executed; regenerate the suggestion."
                )
                changed = True
        normalized.append(record)

    if changed:
        _write_items(normalized)
    return normalized


def _write_items(items: list[dict[str, Any]]) -> None:
    path = get_pending_installs_path()
    with path.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def save_pending_installs(items: list[dict[str, Any]]) -> None:
    _ensure_queue_file()
    _write_items(items)


def _next_id(items: list[dict[str, Any]]) -> int:
    if not items:
        return 1
    return max(int(item.get("id", 0)) for item in items) + 1


def add_install_suggestion(suggestion: dict[str, Any]) -> dict[str, Any]:
    if not STRUCTURED_EXECUTION_FIELDS.issubset(suggestion):
        missing = sorted(STRUCTURED_EXECUTION_FIELDS.difference(suggestion))
        raise ValueError(f"Structured install suggestion is missing fields: {missing}")
    if not isinstance(suggestion.get("args"), list) or not all(
        isinstance(arg, str) for arg in suggestion["args"]
    ):
        raise ValueError("Structured install suggestion args must be list[str]")

    items = load_pending_installs()

    installer_path = suggestion["installer_path"]
    for item in items:
        if item.get("installer_path") == installer_path and item.get("status") == "pending":
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
    return update_install_suggestion_record(record_id, {"status": status})


def update_install_suggestion_record(
    record_id: int,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    items = load_pending_installs()

    for item in items:
        if int(item.get("id", 0)) == int(record_id):
            item.update(updates)
            item["updated_at"] = datetime.now().isoformat(timespec="seconds")
            save_pending_installs(items)
            return item

    return None


def get_pending_items() -> list[dict[str, Any]]:
    return [
        item for item in load_pending_installs()
        if item.get("status") == "pending"
    ]
