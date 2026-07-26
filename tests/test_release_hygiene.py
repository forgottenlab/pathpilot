from __future__ import annotations

import importlib
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app import __version__
from app import cli
from scripts.check_release_artifacts import check_archive


ROOT = Path(__file__).parents[1]


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_dependencies_are_layered() -> None:
    project = _pyproject()["project"]
    runtime = "\n".join(project["dependencies"]).lower()
    extras = project["optional-dependencies"]
    assert "pyside6" not in runtime
    assert "pytest" not in runtime
    assert "questionary" not in runtime
    assert any("pyside6" in item.lower() for item in extras["gui"])
    assert any("pytest>=8,<9" == item.lower() for item in extras["dev"])
    assert {item.lower() for item in extras["all"]} == {
        *{item.lower() for item in extras["gui"]},
        *{item.lower() for item in extras["dev"]},
    }
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "pyside6" not in requirements
    assert "pytest" not in requirements
    assert "questionary" not in requirements


def test_cli_import_does_not_import_pyside6() -> None:
    before = {name for name in sys.modules if name.startswith("PySide6")}
    importlib.reload(cli)
    after = {name for name in sys.modules if name.startswith("PySide6")}
    assert after == before


def test_ui_without_gui_extra_is_clear_nonzero_and_has_no_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = cli.importlib.util.find_spec
    monkeypatch.setattr(
        cli.importlib.util,
        "find_spec",
        lambda name: None if name == "PySide6" else original(name),
    )
    result = CliRunner().invoke(cli.app, ["--lang", "en", "ui"])
    assert result.exit_code == 1
    assert "pathpilot[gui]" in result.stdout
    assert "Traceback" not in result.stdout


def test_canonical_entrypoint_and_dead_entries_removed() -> None:
    scripts = _pyproject()["project"]["scripts"]
    assert scripts == {"pathpilot": "app.cli:main"}
    assert callable(cli.main)
    assert not (ROOT / "main.py").exists()
    assert not (ROOT / "app" / "main.py").exists()
    assert not (ROOT / "app" / "manage_installs.py").exists()


def test_guide_lists_every_real_command_without_duplicate_force_row() -> None:
    output = CliRunner().invoke(cli.app, ["--lang", "en", "commands"])
    assert output.exit_code == 0
    expected = (
        "pathpilot doctor",
        "pathpilot test",
        "pathpilot status",
        "pathpilot watch",
        "pathpilot ui",
        "pathpilot config show",
        "pathpilot config set-root <path>",
        "pathpilot config reset-root",
        "pathpilot sources list",
        "pathpilot sources add <path>",
        "pathpilot sources remove <path>",
        "pathpilot installs list",
        "pathpilot installs detail <id>",
        "pathpilot installs skip <id>",
        "pathpilot installs open <id>",
    )
    for command in expected:
        assert command in output.stdout
    assert output.stdout.count("pathpilot installs run <id>") == 1
    assert output.stdout.count("--force") == 1


def test_key_cli_output_supports_zh_en_and_chinese_first_bilingual() -> None:
    runner = CliRunner()
    english = runner.invoke(cli.app, ["--lang", "en", "config", "reset-root"])
    assert english.exit_code == 0
    assert "Root auto-selection has been restored" in english.stdout
    assert "已重置" not in english.stdout

    bilingual = runner.invoke(cli.app, ["--lang", "bi", "config", "reset-root"])
    assert bilingual.exit_code == 0
    assert "已重置为自动选择根目录。 / Root auto-selection has been restored." in bilingual.stdout
    assert bilingual.stdout.index("已重置") < bilingual.stdout.index("Root auto-selection")

    chinese = runner.invoke(cli.app, ["--lang", "zh", "installs", "list"])
    assert chinese.exit_code == 0
    assert "当前没有符合条件的安装建议" in chinese.stdout


def test_release_documents_metadata_shipgit_and_versions() -> None:
    for name in ("LICENSE", "SECURITY.md", "CHANGELOG.md", "CONTRIBUTING.md"):
        assert (ROOT / name).is_file()
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert license_text.startswith("MIT License")
    assert "Copyright (c) 2026 forgottenlab" in license_text

    project = _pyproject()["project"]
    assert project["version"] == __version__
    assert project["requires-python"] == ">=3.12"
    assert project["license"] == "MIT"
    assert project["urls"]["Repository"] == "https://github.com/forgottenlab/pathpilot"
    assert "Development Status :: 3 - Alpha" in project["classifiers"]
    install_script = (ROOT / "scripts" / "install.ps1").read_text(encoding="utf-8")
    assert f'$InstallerVersion = "{__version__}"' in install_script
    assert "[switch]$CliOnly" in install_script

    shipgit = (ROOT / ".shipgit.yml").read_text(encoding="utf-8")
    assert "defaultBranch: main" in shipgit
    assert "git@github.com:forgottenlab/pathpilot.git" in shipgit
    assert "defaultBranch: master" not in shipgit


def test_uninstaller_retains_user_state_by_default() -> None:
    script = (ROOT / "scripts" / "uninstall.ps1").read_text(encoding="utf-8")
    assert "[switch]$RemoveUserConfig" in script
    assert "if ($RemoveUserConfig)" in script
    removal_index = script.index("Remove-Item -LiteralPath $userState")
    guard_index = script.index("if ($RemoveUserConfig)")
    assert removal_index > guard_index


def test_artifact_checker_accepts_packages_and_rejects_private_state(tmp_path: Path) -> None:
    wheel = tmp_path / "pathpilot-0.2.2-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for prefix in ("app/core/", "app/files/", "app/installers/", "app/gui/"):
            archive.writestr(f"{prefix}__init__.py", "")
    check_archive(wheel)

    bad = tmp_path / "pathpilot-0.2.2.tar.gz"
    with tarfile.open(bad, "w:gz") as archive:
        payload = tmp_path / "pending_installs.json"
        payload.write_text("[]", encoding="utf-8")
        archive.add(payload, arcname="pathpilot-0.2.2/data/pending_installs.json")
    with pytest.raises(RuntimeError, match="forbidden|runtime state"):
        check_archive(bad)


def test_ci_has_core_package_and_gui_jobs() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for fragment in (
        "python-version: [\"3.12\", \"3.13\"]",
        'python -m pip install -e ".[dev]"',
        "python -m build",
        "CLI-only wheel smoke",
        "gui-smoke:",
        "QT_QPA_PLATFORM: offscreen",
        "PowerShell AST",
        "ensure_user_config_files(); load_settings()",
        "Push-Location $env:RUNNER_TEMP",
        "assert m.version('pathpilot') == '0.2.2'",
    ):
        assert fragment in workflow
