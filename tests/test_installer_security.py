from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from app.installers.queue import add_install_suggestion, load_pending_installs
from app.installers.runner import run_install_record
from app.installers.strategy import (
    build_suggestion_from_family,
    build_suggestion_from_known_app,
)


def _make_suggestion(
    tmp_path: Path,
    runtime_paths: dict[str, str],
    *,
    family: str = "inno_setup",
    installer_name: str = "Installer With Spaces.exe",
    target_name: str = "Target With Spaces",
) -> dict[str, Any]:
    installer = (
        Path(runtime_paths["archive_root"])
        / "01-Software"
        / "_IncomingInstallers"
        / installer_name
    )
    installer.parent.mkdir(parents=True, exist_ok=True)
    installer.write_bytes(b"not a real installer")
    target = Path(runtime_paths["apps_root"]) / "General" / target_name
    rule = {"family": family, "mode": "auto"}
    suggestion = build_suggestion_from_family(installer, rule, runtime_paths)
    suggestion["target_dir"] = str(target.resolve(strict=False))
    from app.installers.strategy import rebuild_execution_fields

    suggestion.update(rebuild_execution_fields(suggestion, target))
    return suggestion


def _installers_root(runtime_paths: dict[str, str]) -> Path:
    return Path(runtime_paths["archive_root"]) / "01-Software" / "_IncomingInstallers"


def test_structured_popen_uses_list_and_shell_false(
    tmp_path: Path,
    runtime_paths: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = add_install_suggestion(_make_suggestion(tmp_path, runtime_paths))
    calls: list[tuple[list[str], bool]] = []

    def fake_popen(argv: list[str], *, shell: bool) -> object:
        calls.append((argv, shell))
        return object()

    monkeypatch.setattr("app.installers.runner.subprocess.Popen", fake_popen)
    assert run_install_record(
        record,
        apps_root=runtime_paths["apps_root"],
        installers_root=_installers_root(runtime_paths),
    )
    assert calls[0][1] is False
    assert isinstance(calls[0][0], list)
    assert calls[0][0][0] == record["installer_path"]
    assert " " in calls[0][0][0]
    assert calls[0][0][1].startswith("/DIR=")
    assert "Target With Spaces" in calls[0][0][1]


def test_shell_metacharacters_remain_data_in_single_argument(
    tmp_path: Path,
    runtime_paths: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suggestion = _make_suggestion(
        tmp_path,
        runtime_paths,
        target_name="Data & Pipe | Redirect > In < (Group) ^ Percent % Bang !",
    )
    record = add_install_suggestion(suggestion)
    captured: dict[str, Any] = {}

    def fake_popen(argv: list[str], *, shell: bool) -> object:
        captured["argv"] = argv
        captured["shell"] = shell
        return object()

    monkeypatch.setattr("app.installers.runner.subprocess.Popen", fake_popen)
    assert run_install_record(
        record,
        apps_root=runtime_paths["apps_root"],
        installers_root=_installers_root(runtime_paths),
    )
    assert captured["shell"] is False
    assert len(captured["argv"]) == 2
    assert "&" in captured["argv"][1]
    assert "|" in captured["argv"][1]
    assert ">" in captured["argv"][1]
    assert "<" in captured["argv"][1]
    assert "(" in captured["argv"][1]
    assert ")" in captured["argv"][1]
    assert "^" in captured["argv"][1]
    assert "%" in captured["argv"][1]
    assert "!" in captured["argv"][1]


def test_installer_outside_managed_archive_is_blocked(
    tmp_path: Path,
    runtime_paths: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outside = tmp_path / "outside.exe"
    outside.write_bytes(b"not executable")
    suggestion = build_suggestion_from_family(
        outside,
        {"family": "unknown", "mode": "suggest"},
        runtime_paths,
    )
    record = add_install_suggestion(suggestion)

    def forbidden_popen(*_args: Any, **_kwargs: Any) -> object:
        raise AssertionError("unmanaged installer reached Popen")

    monkeypatch.setattr("app.installers.runner.subprocess.Popen", forbidden_popen)
    assert not run_install_record(
        record,
        apps_root=runtime_paths["apps_root"],
        installers_root=_installers_root(runtime_paths),
    )
    assert load_pending_installs()[0]["status"] == "blocked"


def test_legacy_command_record_is_marked_and_never_executed(
    isolated_pathpilot_home: Path,
    runtime_paths: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.paths import ensure_user_config_files, get_pending_installs_path

    ensure_user_config_files()
    legacy = {
        "id": 1,
        "name": "Legacy",
        "status": "pending",
        "mode": "auto",
        "command": '"unsafe.exe" & calc.exe',
    }
    get_pending_installs_path().write_text(json.dumps([legacy]), encoding="utf-8")
    record = load_pending_installs()[0]
    assert record["status"] == "legacy_unsafe"

    def forbidden_popen(*_args: Any, **_kwargs: Any) -> object:
        raise AssertionError("legacy record reached Popen")

    monkeypatch.setattr("app.installers.runner.subprocess.Popen", forbidden_popen)
    assert not run_install_record(
        record,
        apps_root=runtime_paths["apps_root"],
        installers_root=_installers_root(runtime_paths),
    )


def test_force_cannot_run_legacy_record(isolated_pathpilot_home: Path) -> None:
    from app.core.paths import ensure_user_config_files, get_pending_installs_path

    ensure_user_config_files()
    get_pending_installs_path().write_text(
        json.dumps([
            {
                "id": 1,
                "name": "Legacy",
                "status": "pending",
                "mode": "suggest",
                "command": '"unsafe.exe"',
            }
        ]),
        encoding="utf-8",
    )
    import app.cli as cli

    result = CliRunner().invoke(cli.app, ["installs", "run", "1", "--force"])
    assert result.exit_code != 0
    assert "command-only" in result.output


def test_all_generated_modes_are_suggest(
    tmp_path: Path,
    runtime_paths: dict[str, str],
) -> None:
    installer = tmp_path / "ollama-looking.exe"
    installer.write_bytes(b"inno setup marker only")
    known = build_suggestion_from_known_app(
        installer,
        {
            "name": "Ollama",
            "target": "{apps_root}/Professional/AI/Ollama",
            "family": "inno_setup",
            "mode": "auto",
        },
        runtime_paths,
    )
    family = build_suggestion_from_family(
        installer,
        {"family": "inno_setup", "mode": "auto"},
        runtime_paths,
    )
    assert known["mode"] == "suggest"
    assert family["mode"] == "suggest"


def test_launch_success_and_failure_statuses(
    tmp_path: Path,
    runtime_paths: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = add_install_suggestion(_make_suggestion(tmp_path, runtime_paths, target_name="One"))
    monkeypatch.setattr(
        "app.installers.runner.subprocess.Popen",
        lambda argv, *, shell: object(),
    )
    assert run_install_record(
        first,
        apps_root=runtime_paths["apps_root"],
        installers_root=_installers_root(runtime_paths),
    )
    assert load_pending_installs()[0]["status"] == "launched"

    second = add_install_suggestion(_make_suggestion(
        tmp_path,
        runtime_paths,
        installer_name="Second Installer.exe",
        target_name="Two",
    ))

    def fail_popen(argv: list[str], *, shell: bool) -> object:
        raise OSError("mock launch failure")

    monkeypatch.setattr("app.installers.runner.subprocess.Popen", fail_popen)
    assert not run_install_record(
        second,
        apps_root=runtime_paths["apps_root"],
        installers_root=_installers_root(runtime_paths),
    )
    statuses = {item["id"]: item["status"] for item in load_pending_installs()}
    assert statuses[second["id"]] == "launch_failed"


def test_cli_rejects_unsafe_root_with_nonzero_exit() -> None:
    import app.cli as cli

    result = CliRunner().invoke(cli.app, ["config", "set-root", str(Path.cwd().anchor)])
    assert result.exit_code != 0


def test_force_cannot_bypass_install_target_policy(
    tmp_path: Path,
    runtime_paths: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = add_install_suggestion(_make_suggestion(tmp_path, runtime_paths))
    import app.cli as cli
    cli.save_settings_file({
        "watch_directories": [runtime_paths["user_downloads"]],
        "base_paths": {"root_dir": runtime_paths["root_dir"]},
        "behavior": {},
    })

    def forbidden_popen(*_args: Any, **_kwargs: Any) -> object:
        raise AssertionError("unsafe target reached Popen")

    monkeypatch.setattr("app.installers.runner.subprocess.Popen", forbidden_popen)
    result = CliRunner().invoke(
        cli.app,
        ["installs", "run", str(record["id"]), "--force", "--target", str(tmp_path / "escape")],
    )
    assert result.exit_code != 0


@pytest.fixture
def gui_window(
    runtime_paths: dict[str, str],
):
    pytest.importorskip("PySide6.QtWidgets", reason="GUI extra is not installed")
    from app.core.json_store import atomic_write_json
    from app.core.paths import get_settings_path
    from app.gui.start_gui import create_main_window

    atomic_write_json(get_settings_path(), {
        "watch_directories": [runtime_paths["user_downloads"]],
        "base_paths": {"root_dir": runtime_paths["root_dir"]},
    })
    application, window = create_main_window()
    window.install_page.timer.stop()
    try:
        yield window
    finally:
        window.close()
        window.deleteLater()
        application.processEvents()


def test_gui_skipping_suggestion_refreshes_both_counts(
    gui_window, tmp_path: Path, runtime_paths: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PySide6.QtWidgets import QMessageBox

    page = gui_window.install_page
    add_install_suggestion(_make_suggestion(tmp_path, runtime_paths))
    gui_window.refresh_status_btn.click()
    assert gui_window.status_label.text().endswith("待处理建议：1")
    # Prime the page independently as well, so the skip is exercised on the old GUI.
    page.refresh_btn.click()
    statuses_at_confirmation = []
    monkeypatch.setattr(
        QMessageBox, "information",
        lambda *_: statuses_at_confirmation.append(gui_window.status_label.text()),
    )

    page.skip_btn.click()

    assert load_pending_installs()[0]["status"] == "skipped"
    assert page.table.rowCount() == 0
    assert page.summary_label.text() == "待处理安装建议：0"
    assert gui_window.status_label.text().endswith("待处理建议：0")
    assert statuses_at_confirmation == [gui_window.status_label.text()]


def test_gui_timer_refreshes_both_counts_and_preserves_dirty_target(
    gui_window, tmp_path: Path, runtime_paths: dict[str, str],
) -> None:
    page = gui_window.install_page
    first = add_install_suggestion(_make_suggestion(tmp_path, runtime_paths))
    page.refresh_btn.click()
    assert page.command_edit.isReadOnly()
    edited = str(Path(runtime_paths["apps_root"]) / "General" / "Edited Target")
    page.target_edit.setText(edited)
    page.on_target_edited(edited)

    add_install_suggestion(_make_suggestion(
        tmp_path, runtime_paths, installer_name="Watcher Fixture.exe",
    ))
    page.timer.timeout.emit()

    assert page.table.rowCount() == 2
    assert page.summary_label.text() == "待处理安装建议：2"
    assert gui_window.status_label.text().endswith("待处理建议：2")
    assert page.current_record["id"] == first["id"]
    assert page.target_edit.text() == edited
    assert "Edited Target" in page.command_edit.text()


def test_gui_manual_refresh_and_queue_error(
    gui_window, tmp_path: Path, runtime_paths: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PySide6.QtWidgets import QMessageBox
    from app.core.json_store import reset_json
    from app.core.paths import get_pending_installs_path

    page = gui_window.install_page
    add_install_suggestion(_make_suggestion(tmp_path, runtime_paths))
    gui_window.refresh_status_btn.click()
    assert gui_window.status_label.text().endswith("待处理建议：1")
    assert page.summary_label.text() == "待处理安装建议：1"
    assert page.table.rowCount() == 1

    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda _, title, _message: errors.append(title))
    queue_path = get_pending_installs_path()
    queue_path.write_text("{", encoding="utf-8")
    page.timer.timeout.emit()
    assert page.summary_label.text() == "安装建议队列损坏或被锁定"
    assert gui_window.status_label.text().endswith("待处理建议：队列不可用")
    assert errors == []

    gui_window.refresh_status_btn.click()
    assert errors == ["安装建议队列错误"]
    assert gui_window.status_label.text().endswith("待处理建议：队列不可用")

    reset_json(queue_path, [])
    page.refresh_btn.click()
    assert page.table.rowCount() == 0
    assert page.summary_label.text() == "待处理安装建议：0"
    assert gui_window.status_label.text().endswith("待处理建议：0")


def test_gui_keeps_legacy_rows_out_of_pending_counts(gui_window) -> None:
    from app.core.json_store import reset_json
    from app.core.paths import get_pending_installs_path

    reset_json(get_pending_installs_path(), [{"id": 1, "command": "legacy preview"}])
    gui_window.install_page.refresh_btn.click()

    page = gui_window.install_page
    assert page.table.rowCount() == 1
    assert page.table.item(0, 5).text() == "legacy_unsafe"
    assert page.summary_label.text() == "待处理安装建议：0"
    assert gui_window.status_label.text().endswith("待处理建议：0")


def test_stale_gui_and_cli_skip_cannot_overwrite_claim(
    gui_window, tmp_path: Path, runtime_paths: dict[str, str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PySide6.QtWidgets import QMessageBox
    from app.cli import app
    from app.installers.queue import claim_install_suggestion

    record = add_install_suggestion(_make_suggestion(tmp_path, runtime_paths))
    page = gui_window.install_page
    page.refresh_btn.click()
    assert page.skip_btn.isEnabled()
    claimed = claim_install_suggestion(record["id"])
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _, title, msg: warnings.append(title))
    monkeypatch.setattr(QMessageBox, "information", lambda *_: pytest.fail("unexpected success dialog"))

    page.skip_btn.click()
    assert warnings == ["无法跳过"]
    assert page.table.item(0, 5).text() == "claimed"
    assert not page.skip_btn.isEnabled()
    assert not page.run_recommended_btn.isEnabled()
    assert gui_window.status_label.text().endswith("待处理建议：0")
    assert CliRunner().invoke(app, ["installs", "skip", str(record["id"])]).exit_code == 1
    assert load_pending_installs() == [claimed]
