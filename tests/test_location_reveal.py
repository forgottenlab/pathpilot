from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def shell_calls(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    calls: list[Path] = []
    monkeypatch.setattr(os, "startfile", lambda path, *a, **kw: calls.append(Path(path)), raising=False)

    def forbidden_launch(*args, **kwargs):
        raise AssertionError("Location actions must not launch a subprocess")

    monkeypatch.setattr("subprocess.Popen", forbidden_launch)
    return calls


@pytest.fixture
def install_page(shell_calls, monkeypatch):
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication, QMessageBox
    from app.gui.install_page import InstallPage

    application = QApplication.instance() or QApplication([])
    page = InstallPage()
    page.timer.stop()
    page.location_warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: page.location_warnings.append(args))
    try:
        yield page
    finally:
        page.close()
        application.processEvents()


@pytest.mark.parametrize("suffix", [".exe", ".msi", ".txt"])
def test_installer_location_button_opens_parent_not_file(tmp_path, install_page, shell_calls, suffix):
    installer = tmp_path / f"Fixture With Spaces & Data{suffix}"
    installer.write_bytes(b"inert fixture - never execute")
    install_page.current_record = {"installer_path": str(installer), "status": "pending"}
    install_page.open_installer_btn.click()
    assert shell_calls == [installer.parent]
    assert installer not in shell_calls
    assert install_page.current_record["status"] == "pending"


@pytest.mark.parametrize("legacy", [False, True])
def test_missing_installer_reveals_existing_parent(tmp_path, install_page, shell_calls, legacy):
    field = "installer" if legacy else "installer_path"
    install_page.current_record = {field: str(tmp_path / "missing.exe"), "status": "legacy_unsafe" if legacy else "pending"}
    before = dict(install_page.current_record)
    install_page.open_installer_btn.click()
    assert shell_calls == [tmp_path]
    assert install_page.current_record == before


@pytest.mark.parametrize("value", ["", "   ", None, "missing-parent", "invalid-nul"])
def test_invalid_installer_location_does_not_open_anything(tmp_path, install_page, shell_calls, value):
    if value == "missing-parent":
        value = str(tmp_path / "absent" / "fixture.exe")
    elif value == "invalid-nul":
        value = "bad\x00path"
    install_page.current_record = {"installer_path": value}
    install_page.open_installer_btn.click()
    assert shell_calls == []
    assert install_page.location_warnings


@pytest.mark.parametrize("kind", ["directory", "file", "missing", "empty"])
def test_target_button_only_opens_existing_directory(tmp_path, install_page, shell_calls, kind):
    target = tmp_path / "target"
    if kind == "directory":
        target.mkdir()
    elif kind == "file":
        target.write_bytes(b"not executable")
    install_page.current_record = {"status": "pending"}
    install_page.target_edit.setText("" if kind == "empty" else str(target))
    install_page.open_target_btn.click()
    assert shell_calls == ([target] if kind == "directory" else [])
    assert bool(install_page.location_warnings) == (kind != "directory")


def test_shell_open_error_is_reported_without_gui_traceback(tmp_path, install_page, monkeypatch):
    def denied(*args, **kwargs):
        raise OSError("mock Explorer failure")

    monkeypatch.setattr(os, "startfile", denied)
    install_page.current_record = {"installer_path": str(tmp_path / "missing.msi")}
    install_page.open_installer_btn.click()
    assert install_page.location_warnings


def test_directory_helper_uses_directory_verb(tmp_path, shell_calls, monkeypatch):
    from app.gui.ui_helpers import open_directory_in_explorer

    calls = []
    monkeypatch.setattr(os, "startfile", lambda path, operation: calls.append((Path(path), operation)))
    assert open_directory_in_explorer(tmp_path)
    assert calls == [(tmp_path, "explore")]


@pytest.mark.parametrize("kind", ["file", "missing", "empty", "nul"])
def test_directory_helper_rejects_non_directories(tmp_path, shell_calls, kind):
    from app.gui.ui_helpers import open_directory_in_explorer

    target = tmp_path / "fixture.exe"
    if kind == "file":
        target.write_bytes(b"inert")
    value = "" if kind == "empty" else "bad\x00path" if kind == "nul" else target
    assert not open_directory_in_explorer(value)
    assert shell_calls == []


def test_main_window_directory_buttons_do_not_open_files(tmp_path, shell_calls):
    pytest.importorskip("PySide6.QtWidgets")
    from app.gui.start_gui import create_main_window

    application, window = create_main_window()
    window.install_page.timer.stop()
    try:
        window.runtime_paths["root_dir"] = str(tmp_path)
        window.open_root_btn.click()
        assert shell_calls == [tmp_path]
        file = tmp_path / "not-a-directory.exe"
        file.write_bytes(b"inert")
        window.runtime_paths["incoming_root"] = str(file)
        window.open_incoming_btn.click()
        assert shell_calls == [tmp_path]
    finally:
        window.close()
        application.processEvents()


def test_production_has_no_shell_true_or_ambiguous_open_helper():
    import ast

    root = Path(__file__).parents[1] / "app"
    for path in root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "open_in_explorer" not in source
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call):
                assert not any(
                    item.arg == "shell" and isinstance(item.value, ast.Constant) and item.value.value is True
                    for item in node.keywords
                ), str(path)


@pytest.mark.parametrize("suffix", [".exe", ".msi", ".txt"])
def test_cli_installs_open_only_opens_parent(tmp_path, monkeypatch, shell_calls, suffix):
    from typer.testing import CliRunner
    from app import cli

    installer = tmp_path / f"fixture{suffix}"
    installer.write_bytes(b"inert fixture")
    monkeypatch.setattr(cli, "load_install_items_or_exit", lambda: [{"id": 1, "installer_path": str(installer)}])
    result = CliRunner().invoke(cli.app, ["installs", "open", "1"])
    assert result.exit_code == 0
    assert shell_calls == [installer.parent]
