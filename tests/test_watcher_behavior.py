from __future__ import annotations

from pathlib import Path

import pytest

from app.core.json_store import atomic_write_json
from app.core.paths import DEFAULT_SETTINGS, ensure_user_config_files, get_settings_path
from app.core.settings import load_rules, load_settings
from app.files.watcher import DownloadEventHandler
from app.installers.queue import load_pending_installs


@pytest.fixture
def watcher_state(tmp_path: Path) -> tuple[DownloadEventHandler, dict, Path]:
    source = tmp_path / "source"
    root = tmp_path / "managed"
    source.mkdir()
    ensure_user_config_files()
    settings_data = {
        **DEFAULT_SETTINGS,
        "watch_directories": [str(source)],
        "base_paths": {"root_dir": str(root)},
        "behavior": {
            "ignore_hidden_files": True,
            "stable_check_seconds": 0,
            "stable_checks": 1,
            "create_missing_dirs": True,
            "overwrite_strategy": "rename",
        },
    }
    atomic_write_json(get_settings_path(), settings_data)
    settings = load_settings()
    handler = DownloadEventHandler(settings, load_rules())
    return handler, settings["runtime_paths"], source


def _process_two_stages(
    handler: DownloadEventHandler,
    runtime: dict,
    source: Path,
    name: str,
    content: bytes = b"fixture",
) -> Path:
    original = source / name
    original.write_bytes(content)
    handler._handle_file(original)
    incoming = Path(runtime["incoming_root"]) / name
    assert incoming.exists()
    handler._handle_file(incoming)
    return incoming


@pytest.mark.parametrize(
    ("name", "relative_target"),
    [
        ("notes.txt", Path("05-Documents/Mixed/notes.txt")),
        ("tool.py", Path("06-Code/Python/tool.py")),
        ("archive.zip", Path("07-Archives/_IncomingArchives/archive.zip")),
    ],
)
def test_watcher_classifies_files_to_final_directory(
    watcher_state: tuple[DownloadEventHandler, dict, Path],
    name: str,
    relative_target: Path,
) -> None:
    handler, runtime, source = watcher_state
    incoming = _process_two_stages(handler, runtime, source, name)
    final = Path(runtime["archive_root"]) / relative_target
    assert final.exists()
    assert not incoming.exists()


def test_exe_is_archived_and_creates_structured_pending_suggestion(
    watcher_state: tuple[DownloadEventHandler, dict, Path],
) -> None:
    handler, runtime, source = watcher_state
    incoming = _process_two_stages(
        handler,
        runtime,
        source,
        "safe-fixture.exe",
        b"MZ inert fixture Inno Setup",
    )
    final = Path(runtime["archive_root"]) / "01-Software" / "_IncomingInstallers" / "safe-fixture.exe"
    assert final.exists() and not incoming.exists()

    records = load_pending_installs()
    assert len(records) == 1
    record = records[0]
    for field in (
        "executable",
        "args",
        "preview",
        "installer_path",
        "target_dir",
        "installer_family",
    ):
        assert record[field]
    assert record["mode"] == "suggest"
    assert record["status"] == "pending"
    assert Path(record["installer_path"]) == final.resolve()


def test_same_name_does_not_overwrite(
    watcher_state: tuple[DownloadEventHandler, dict, Path],
) -> None:
    handler, runtime, source = watcher_state
    target_dir = Path(runtime["archive_root"]) / "05-Documents" / "Mixed"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "same.txt").write_text("existing", encoding="utf-8")
    _process_two_stages(handler, runtime, source, "same.txt", b"new")
    assert (target_dir / "same.txt").read_text(encoding="utf-8") == "existing"
    assert (target_dir / "same (1).txt").read_bytes() == b"new"


def test_temporary_download_suffix_is_ignored(
    watcher_state: tuple[DownloadEventHandler, dict, Path],
) -> None:
    handler, _runtime, source = watcher_state
    fixture = source / "still-downloading.crdownload"
    fixture.write_bytes(b"partial")
    handler._handle_file(fixture)
    assert fixture.exists()


def test_unstable_file_is_not_moved(
    watcher_state: tuple[DownloadEventHandler, dict, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler, _runtime, source = watcher_state
    fixture = source / "changing.txt"
    fixture.write_bytes(b"partial")
    monkeypatch.setattr("app.files.watcher.wait_until_file_stable", lambda *_a, **_k: False)
    handler._handle_file(fixture)
    assert fixture.exists()


def test_duplicate_installer_event_does_not_duplicate_pending_record(
    watcher_state: tuple[DownloadEventHandler, dict, Path],
) -> None:
    handler, runtime, source = watcher_state
    _process_two_stages(handler, runtime, source, "duplicate.exe", b"MZ inert fixture")
    installer = Path(runtime["archive_root"]) / "01-Software" / "_IncomingInstallers" / "duplicate.exe"
    handler._try_handle_installer(installer)
    assert len(load_pending_installs()) == 1
