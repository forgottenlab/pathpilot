from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from app import cli
from app.core.paths import get_settings_path
from app.diagnostics import run_doctor_report, run_self_test


def test_doctor_is_read_only_for_missing_home(isolated_pathpilot_home: Path) -> None:
    assert not isolated_pathpilot_home.exists()
    assert run_doctor_report("en") is False
    assert not isolated_pathpilot_home.exists()


def test_doctor_reports_corrupt_json_without_mutating_it(
    isolated_pathpilot_home: Path,
) -> None:
    settings = get_settings_path()
    settings.parent.mkdir(parents=True)
    settings.write_text("{broken", encoding="utf-8")
    before = settings.read_bytes()

    assert run_doctor_report("en") is False
    assert settings.read_bytes() == before
    assert list(settings.parent.glob("settings.json.*.corrupt")) == []


def test_cli_returns_clear_error_and_preserves_corrupt_backup() -> None:
    settings = get_settings_path()
    settings.parent.mkdir(parents=True)
    settings.write_text("{broken", encoding="utf-8")

    result = CliRunner().invoke(cli.app, ["config", "show"])
    assert result.exit_code == 1
    assert "State file error" in result.stdout or "状态文件错误" in result.stdout
    assert not settings.exists()
    backups = list(settings.parent.glob("settings.json.*.corrupt"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{broken"
    assert run_doctor_report("en") is False


def test_self_test_uses_its_own_temporary_home(isolated_pathpilot_home: Path) -> None:
    assert run_self_test("en") is True
    assert not isolated_pathpilot_home.exists()


def test_full_check_has_no_real_user_home_or_cross_drive_cleanup() -> None:
    script = (Path(__file__).parents[1] / "scripts" / "full_check.ps1").read_text(
        encoding="utf-8"
    )
    forbidden = ("USERPROFILE", ".pathpilot", "Get-PSDrive", "Backup-PathPilotUserData")
    assert all(item not in script for item in forbidden)
    assert "PATHPILOT_HOME" in script
    assert "finally" in script
