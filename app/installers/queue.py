from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.json_store import atomic_write_json, ensure_json_file, read_json, update_json
from app.core.paths import get_pending_installs_path


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
    ensure_json_file(get_pending_installs_path(), [], expected_type=list)


def _normalize_items(data: list[Any]) -> tuple[list[dict[str, Any]], bool]:
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
    return normalized, changed


def load_pending_installs(
    *,
    create_missing: bool = True,
    lock_timeout: float = 5.0,
) -> list[dict[str, Any]]:
    path = get_pending_installs_path()
    if create_missing:
        _ensure_queue_file()

    data = read_json(path, expected_type=list, lock_timeout=lock_timeout)
    normalized, changed = _normalize_items(data)
    if not changed:
        return normalized

    def normalize_current(current: list[Any]) -> list[dict[str, Any]]:
        final, _ = _normalize_items(current)
        current[:] = final
        return final

    return update_json(
        path,
        normalize_current,
        default=[],
        expected_type=list,
        lock_timeout=lock_timeout,
    )


def save_pending_installs(
    items: list[dict[str, Any]],
    *,
    lock_timeout: float = 5.0,
) -> None:
    _ensure_queue_file()
    atomic_write_json(get_pending_installs_path(), items, lock_timeout=lock_timeout)


def _next_id(items: list[dict[str, Any]]) -> int:
    if not items:
        return 1
    return max(int(item.get("id", 0)) for item in items) + 1


def add_install_suggestion(
    suggestion: dict[str, Any],
    *,
    lock_timeout: float = 5.0,
) -> dict[str, Any]:
    if not STRUCTURED_EXECUTION_FIELDS.issubset(suggestion):
        missing = sorted(STRUCTURED_EXECUTION_FIELDS.difference(suggestion))
        raise ValueError(f"Structured install suggestion is missing fields: {missing}")
    if not isinstance(suggestion.get("args"), list) or not all(
        isinstance(arg, str) for arg in suggestion["args"]
    ):
        raise ValueError("Structured install suggestion args must be list[str]")

    _ensure_queue_file()
    result: dict[str, Any] = {}

    def add_record(current: list[Any]) -> dict[str, Any]:
        nonlocal result
        items, _ = _normalize_items(current)
        installer_path = suggestion["installer_path"]
        for item in items:
            if item.get("installer_path") == installer_path and item.get("status") == "pending":
                current[:] = items
                result = item
                return item

        record = {
            "id": _next_id(items),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": "pending",
            **suggestion,
        }
        items.append(record)
        current[:] = items
        result = record
        return record

    update_json(
        get_pending_installs_path(),
        add_record,
        default=[],
        expected_type=list,
        lock_timeout=lock_timeout,
    )
    return result


def update_install_suggestion_status(record_id: int, status: str) -> dict[str, Any] | None:
    return update_install_suggestion_record(record_id, {"status": status})


def update_install_suggestion_record(
    record_id: int,
    updates: dict[str, Any],
    *,
    lock_timeout: float = 5.0,
) -> dict[str, Any] | None:
    _ensure_queue_file()
    result: dict[str, Any] | None = None

    def update_record(current: list[Any]) -> dict[str, Any] | None:
        nonlocal result
        items, _ = _normalize_items(current)
        current[:] = items
        for item in items:
            if int(item.get("id", 0)) == int(record_id):
                item.update(updates)
                item["updated_at"] = datetime.now().isoformat(timespec="seconds")
                result = item
                return item
        return None

    update_json(
        get_pending_installs_path(),
        update_record,
        default=[],
        expected_type=list,
        lock_timeout=lock_timeout,
    )
    return result


def get_pending_items() -> list[dict[str, Any]]:
    return [
        item for item in load_pending_installs()
        if item.get("status") == "pending"
    ]
