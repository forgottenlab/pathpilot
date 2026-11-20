from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.core.json_store import ensure_json_file, read_json, update_json
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


def _has_structured_execution(record: dict[str, Any]) -> bool:
    return (
        all(isinstance(record.get(key), str) for key in STRUCTURED_EXECUTION_FIELDS - {"args"})
        and isinstance(record.get("args"), list)
        and all(isinstance(arg, str) for arg in record["args"])
    )


def _normalize_items(data: list[Any]) -> tuple[list[dict[str, Any]], bool]:
    normalized: list[dict[str, Any]] = []
    changed = False
    for item in data:
        if not isinstance(item, dict):
            changed = True
            continue
        record = dict(item)
        if not _has_structured_execution(record) and "command" in record:
            if record.get("status") not in {"legacy_unsafe", "skipped"}:
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
            **suggestion,
            "id": _next_id(items),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": "pending",
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


def _transition_record(
    record_id: int,
    transition: Callable[[dict[str, Any]], dict[str, Any] | None],
) -> dict[str, Any] | None:
    def update_record(current: list[Any]) -> dict[str, Any] | None:
        items, _ = _normalize_items(current)
        current[:] = items
        for item in items:
            if int(item.get("id", 0)) == int(record_id):
                updates = transition(item)
                if updates is None:
                    return None
                item.update(updates)
                item["updated_at"] = datetime.now().isoformat(timespec="seconds")
                return item
        return None

    return update_json(get_pending_installs_path(), update_record, default=[], expected_type=list)


def claim_install_suggestion(
    record_id: int,
    *,
    expected_record: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Claim the current pending snapshot only if its reviewed execution fields still match."""

    def claim(record: dict[str, Any]) -> dict[str, Any] | None:
        if record.get("status") != "pending" or not _has_structured_execution(record):
            return None
        if expected_record is not None and (
            expected_record.get("status") != "pending"
            or any(record[key] != expected_record.get(key) for key in STRUCTURED_EXECUTION_FIELDS)
        ):
            return None
        return {"status": "claimed", "claim_id": uuid4().hex}

    return _transition_record(record_id, claim)


def _transition_claim(
    record_id: int, claim_id: str, expected_status: str, updates: dict[str, Any],
) -> dict[str, Any] | None:
    def advance(record: dict[str, Any]) -> dict[str, Any] | None:
        if (
            claim_id
            and record.get("claim_id") == claim_id
            and record.get("status") == expected_status
        ):
            return updates
        return None

    return _transition_record(record_id, advance)


def prepare_install_launch(
    record_id: int, claim_id: str, fields: dict[str, Any],
) -> dict[str, Any] | None:
    """Persist the validated argv before Popen. An interrupted launch must not be retried."""
    updates = {key: fields[key] for key in STRUCTURED_EXECUTION_FIELDS - {"mode"}}
    updates["confirmed_at"] = datetime.now().isoformat(timespec="seconds")
    updates["status"] = "launching"
    return _transition_claim(record_id, claim_id, "claimed", updates)


def finish_install_claim(
    record_id: int, claim_id: str, status: str,
) -> dict[str, Any] | None:
    if status == "blocked":
        expected = "claimed"
    elif status in {"launched", "launch_failed", "launch_unknown"}:
        expected = "launching"
    else:
        raise ValueError(f"Invalid install claim outcome: {status}")
    return _transition_claim(record_id, claim_id, expected, {"status": status})


def skip_install_suggestion(record_id: int) -> dict[str, Any] | None:
    def skip(record: dict[str, Any]) -> dict[str, Any] | None:
        if record.get("status") in {"pending", "legacy_unsafe"}:
            return {"status": "skipped"}
        return None

    return _transition_record(record_id, skip)


def get_pending_items() -> list[dict[str, Any]]:
    return [
        item for item in load_pending_installs()
        if item.get("status") == "pending"
    ]
