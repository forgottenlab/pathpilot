from __future__ import annotations

import importlib
import re
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app import __version__
from app import cli
from scripts.check_release_artifacts import (
    REQUIRED_SDIST_FILES,
    REQUIRED_WHEEL_FILES,
    check_archive,
)


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
    for name in (
        "LICENSE",
        "SECURITY.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "README.md",
        "README.zh-CN.md",
    ):
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
        for readme in ("README.md", "README.zh-CN.md"):
            archive.writestr(
                f"pathpilot-0.2.2.data/data/share/doc/pathpilot/{readme}", "docs"
            )
    check_archive(wheel)

    bad = tmp_path / "pathpilot-0.2.2.tar.gz"
    with tarfile.open(bad, "w:gz") as archive:
        payload = tmp_path / "pending_installs.json"
        payload.write_text("[]", encoding="utf-8")
        archive.add(payload, arcname="pathpilot-0.2.2/data/pending_installs.json")
    with pytest.raises(RuntimeError, match="forbidden|runtime state"):
        check_archive(bad)


def test_readmes_are_split_by_language_and_match_the_release_contract() -> None:
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    language_links = "[English](README.md) | [简体中文](README.zh-CN.md)"
    assert language_links in english
    assert language_links in chinese

    required_terms = (
        "0.2.2",
        "CLI-only",
        "GUI extra",
        "PATHPILOT_HOME",
        "doctor",
        "test",
        "suggest",
        "legacy_unsafe",
        "launched",
        "--force",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "MIT License",
    )
    for readme in (english, chinese):
        for term in required_terms:
            assert term in readme

    real_commands = (
        "pathpilot guide",
        "pathpilot commands",
        "pathpilot doctor",
        "pathpilot test",
        "pathpilot status",
        "pathpilot watch",
        "pathpilot ui",
        "pathpilot version",
        "pathpilot config show",
        "pathpilot config set-root <path>",
        "pathpilot config reset-root",
        "pathpilot sources list",
        "pathpilot sources add <path>",
        "pathpilot sources remove <path>",
        "pathpilot installs list [--all]",
        "pathpilot installs detail <id>",
        "pathpilot installs run <id> --force",
        "pathpilot installs skip <id>",
        "pathpilot installs open <id>",
    )
    for readme in (english, chinese):
        assert all(command in readme for command in real_commands)

    assert "## Requirements /" not in english
    assert "Windows 下载整理与安全安装建议治理工具" not in english
    assert "## 环境要求 /" not in chinese
    assert "PathPilot 解决什么问题" in chinese
    assert "只生成保守、可审查的安装建议" in chinese

    project = _pyproject()["project"]
    assert project["readme"] == "README.md"
    data_files = _pyproject()["tool"]["setuptools"]["data-files"]
    assert set(data_files["share/doc/pathpilot"]) == {"README.md", "README.zh-CN.md"}
    assert REQUIRED_WHEEL_FILES == {"README.md", "README.zh-CN.md"}
    assert {"README.md", "README.zh-CN.md"}.issubset(REQUIRED_SDIST_FILES)

    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "include README.md" in manifest
    assert "include README.zh-CN.md" in manifest


def _workflow_job_block(workflow: str, job_name: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(job_name)}:\n(?P<body>.*?)(?=^  [a-zA-Z][a-zA-Z0-9_-]*:\n|\Z)",
        workflow,
    )
    assert match is not None, f"missing workflow job: {job_name}"
    return match.group("body")


def test_ci_has_core_package_and_gui_jobs() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for fragment in (
        "python-version: [\"3.12\", \"3.13\"]",
        'python -m pip install -e ".[dev]"',
        "python -m build",
        "Create CLI-only smoke environment",
        "Install CLI-only wheel",
        "gui-smoke:",
        "QT_QPA_PLATFORM: offscreen",
        "PowerShell AST",
        "ensure_user_config_files(); load_settings()",
        "Push-Location $env:RUNNER_TEMP",
        "assert m.version('pathpilot') == '0.2.2'",
    ):
        assert fragment in workflow


def test_ci_configures_isolated_home_at_runtime_for_each_job() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "PATHPILOT_HOME: ${{ runner.temp }}" not in workflow
    assert "C:\\Users\\" not in workflow

    expected = {
        "core": (
            "pathpilot-core-${{ matrix.python-version }}",
            "python -m pip install",
        ),
        "package": ("pathpilot-package", "python -m build"),
        "gui-smoke": ("pathpilot-gui", "Install GUI extra and create window offscreen"),
    }
    for job_name, (home_suffix, first_operation) in expected.items():
        block = _workflow_job_block(workflow, job_name)
        configure_at = block.index("- name: Configure isolated PathPilot state")
        checkout_at = block.index("- uses: actions/checkout@v4")
        operation_at = block.index(first_operation)

        assert "QT_QPA_PLATFORM: offscreen" in block
        assert f"$env:RUNNER_TEMP\\{home_suffix}" in block
        assert "Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append" in block
        assert configure_at < checkout_at < operation_at

    core = _workflow_job_block(workflow, "core")
    assert 'python-version: ["3.12", "3.13"]' in core
    package = _workflow_job_block(workflow, "package")
    assert "Create CLI-only smoke environment" in package
    assert "Install CLI-only wheel" in package
    assert "gui-smoke:" in workflow


def test_ci_runtime_checks_are_split_and_expected_ui_failure_is_captured() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    core = _workflow_job_block(workflow, "core")
    core_steps = (
        "CLI help smoke",
        "Initialize isolated PathPilot state",
        "Read-only doctor",
        "Isolated behavior test",
    )
    core_positions = [core.index(f"- name: {name}") for name in core_steps]
    assert core_positions == sorted(core_positions)
    assert core.index("ensure_user_config_files(); load_settings()") < core.index(
        "pathpilot doctor"
    )

    package = _workflow_job_block(workflow, "package")
    package_steps = (
        "Create CLI-only smoke environment",
        "Install CLI-only wheel",
        "Verify PySide6 is absent",
        "CLI-only help and status",
        "Initialize isolated CLI-only state",
        "CLI-only doctor",
        "CLI-only behavior test",
        "Verify GUI extra missing message",
    )
    package_positions = [package.index(f"- name: {name}") for name in package_steps]
    assert package_positions == sorted(package_positions)
    assert package.index("ensure_user_config_files(); load_settings()") < package.index(
        "CLI_SMOKE_PATHPILOT doctor"
    )
    assert "$PSNativeCommandUseErrorActionPreference = $false" in package
    assert "$uiExitCode = $LASTEXITCODE" in package
    assert "$uiText = $uiOutput | Out-String" in package
    assert "$uiExitCode -eq 0" in package
    assert '$uiText -notmatch "pathpilot\\[gui\\]"' in package
    assert '$uiText -match "Traceback"' in package

    assert 'python-version: ["3.12", "3.13"]' in core
    assert "QT_QPA_PLATFORM: offscreen" in core
    assert "QT_QPA_PLATFORM: offscreen" in package
    assert "gui-smoke:" in workflow
    assert "Install GUI extra and create window offscreen" in workflow
    assert "C:\\Users\\" not in workflow
    assert "token" not in workflow.lower()
