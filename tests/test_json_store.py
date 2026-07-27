from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.core import json_store
from app.core.json_store import (
    InterProcessFileLock,
    JsonCorruptError,
    JsonLockTimeout,
    JsonStoreError,
    atomic_write_json,
    ensure_json_file,
    read_json,
)
from app.core.paths import ensure_user_config_files, get_app_home, get_settings_path
from app.core.settings import load_settings
from app.installers.queue import add_install_suggestion, load_pending_installs


def _suggestion(index: int, root: Path) -> dict:
    installer = root / "Downloads" / "01-Software" / "_IncomingInstallers" / f"setup-{index}.exe"
    target = root / "Apps" / "General" / "Utilities" / f"app-{index}"
    return {
        "name": f"setup-{index}",
        "source": "family",
        "executable": str(installer),
        "args": [],
        "preview": str(installer),
        "installer_path": str(installer),
        "target_dir": str(target),
        "installer_family": "unknown",
        "mode": "suggest",
    }


def test_atomic_write_success(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    atomic_write_json(target, {"value": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"value": 2}


def test_replace_failure_preserves_old_file_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "settings.json"
    atomic_write_json(target, {"value": "old"})

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(json_store.os, "replace", fail_replace)
    with pytest.raises(JsonStoreError, match="simulated replace failure"):
        atomic_write_json(target, {"value": "new"})

    assert read_json(target, expected_type=dict) == {"value": "old"}
    assert list(tmp_path.glob(".settings.json.*.tmp")) == []


def test_corrupt_json_is_backed_up_and_not_silently_recreated(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    target.write_text("{not-json", encoding="utf-8")

    with pytest.raises(JsonCorruptError) as raised:
        read_json(target, expected_type=dict)

    backup = raised.value.backup_path
    assert backup is not None and backup.exists()
    assert backup.read_text(encoding="utf-8") == "{not-json"
    assert not target.exists()
    with pytest.raises(JsonCorruptError, match="explicit reset"):
        ensure_json_file(target, {"default": True}, expected_type=dict)
    assert not target.exists()


def test_lock_timeout_fails_without_changing_file(tmp_path: Path) -> None:
    target = tmp_path / "queue.json"
    atomic_write_json(target, [{"old": True}])
    before = target.read_bytes()

    with InterProcessFileLock(target, timeout=1):
        with pytest.raises(JsonLockTimeout):
            atomic_write_json(target, [], lock_timeout=0.05)

    assert target.read_bytes() == before


def test_concurrent_queue_writers_do_not_lose_records(tmp_path: Path) -> None:
    root = tmp_path / "managed"
    with ThreadPoolExecutor(max_workers=8) as pool:
        records = list(pool.map(lambda i: add_install_suggestion(_suggestion(i, root)), range(24)))

    items = load_pending_installs()
    assert len(items) == 24
    assert len({item["id"] for item in items}) == 24
    assert {item["installer_path"] for item in items} == {
        record["installer_path"] for record in records
    }


def test_queue_readers_only_observe_complete_snapshots_during_writes(tmp_path: Path) -> None:
    root = tmp_path / "managed"
    start = threading.Event()
    observed: list[int] = []

    def writer() -> None:
        start.wait()
        for index in range(12):
            add_install_suggestion(_suggestion(index, root))

    def reader() -> None:
        start.wait()
        for _ in range(30):
            observed.append(len(load_pending_installs()))

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(writer), pool.submit(reader), pool.submit(reader)]
        start.set()
        for future in futures:
            future.result()

    assert observed
    assert all(0 <= count <= 12 for count in observed)
    assert len(load_pending_installs()) == 12


def test_pathpilot_home_is_dynamic_before_and_after_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "first-home"
    second = tmp_path / "second-home"

    monkeypatch.setenv("PATHPILOT_HOME", str(first))
    ensure_user_config_files()
    assert get_app_home() == first.resolve()
    assert get_settings_path().is_relative_to(first)
    first_settings = load_settings()
    assert Path(first_settings["runtime_paths"]["root_dir"]).is_relative_to(tmp_path)
    assert Path(first_settings["runtime_paths"]["user_downloads"]).is_relative_to(tmp_path)

    monkeypatch.setenv("PATHPILOT_HOME", str(second))
    ensure_user_config_files()
    assert get_app_home() == second.resolve()
    assert get_settings_path().is_relative_to(second)
    second_settings = load_settings()
    assert Path(second_settings["runtime_paths"]["root_dir"]).is_relative_to(tmp_path)
    assert Path(second_settings["runtime_paths"]["user_downloads"]).is_relative_to(tmp_path)
    assert (first / "config" / "settings.json").exists()
    assert (second / "config" / "settings.json").exists()
