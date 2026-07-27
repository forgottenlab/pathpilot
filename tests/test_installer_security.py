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


def test_gui_command_preview_is_read_only_and_refresh_preserves_dirty_target(
    tmp_path: Path,
    runtime_paths: dict[str, str],
) -> None:
    pytest.importorskip("PySide6.QtWidgets", reason="GUI extra is not installed")
    from PySide6.QtWidgets import QApplication
    from app.gui.install_page import InstallPage

    add_install_suggestion(_make_suggestion(tmp_path, runtime_paths))
    application = QApplication.instance() or QApplication([])
    page = InstallPage()
    try:
        assert page.command_edit.isReadOnly()
        edited = str(Path(runtime_paths["apps_root"]) / "General" / "Edited Target")
        page.target_edit.setText(edited)
        page.on_target_edited(edited)
        page.refresh_table_silent()
        assert page.target_edit.text() == edited
    finally:
        page.timer.stop()
        page.close()
        application.processEvents()
