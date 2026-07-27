from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.core.path_policy import (
    PathPolicyError,
    normalize_path,
    paths_overlap,
    validate_install_target,
    validate_root_directory,
    validate_source_directory,
)


def test_drive_root_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(PathPolicyError):
        validate_root_directory(Path(tmp_path.anchor))


@pytest.mark.parametrize(
    "environment_name,fallback",
    [
        ("SystemRoot", r"C:\Windows"),
        ("ProgramFiles", r"C:\Program Files"),
        ("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ("ProgramData", r"C:\ProgramData"),
    ],
)
def test_windows_protected_directories_are_rejected(
    environment_name: str,
    fallback: str,
) -> None:
    protected = os.environ.get(environment_name, fallback)
    with pytest.raises(PathPolicyError):
        validate_root_directory(protected)


def test_real_pathpilot_home_is_rejected() -> None:
    with pytest.raises(PathPolicyError):
        validate_root_directory(Path.home() / ".pathpilot")


def test_apps_cannot_be_external_source(runtime_paths: dict[str, str]) -> None:
    with pytest.raises(PathPolicyError):
        validate_source_directory(runtime_paths["apps_root"], runtime_paths)


def test_normal_downloads_are_allowed(runtime_paths: dict[str, str]) -> None:
    source = validate_source_directory(runtime_paths["user_downloads"], runtime_paths)
    assert source == normalize_path(runtime_paths["user_downloads"])


def test_apps_child_is_valid_install_target(runtime_paths: dict[str, str]) -> None:
    target = Path(runtime_paths["apps_root"]) / "Professional" / "Example App"
    assert validate_install_target(target, runtime_paths["apps_root"]) == normalize_path(target)


def test_install_target_cannot_escape_apps(runtime_paths: dict[str, str]) -> None:
    escaped = Path(runtime_paths["apps_root"]) / ".." / "Outside"
    with pytest.raises(PathPolicyError):
        validate_install_target(escaped, runtime_paths["apps_root"])


def test_source_and_root_ancestor_overlap_is_rejected(
    runtime_paths: dict[str, str],
) -> None:
    source = Path(runtime_paths["root_dir"]).parent
    with pytest.raises(PathPolicyError):
        validate_root_directory(runtime_paths["root_dir"], [source])
    assert paths_overlap(source, runtime_paths["root_dir"])


def test_watcher_fails_closed_before_creating_managed_source(
    runtime_paths: dict[str, str],
) -> None:
    from app.files.watcher import start_watching

    settings = {
        "runtime_paths": runtime_paths,
        "watch_directories": [runtime_paths["apps_root"]],
        "behavior": {},
    }
    with pytest.raises(PathPolicyError):
        start_watching(settings, {"rules": []})
    assert not Path(runtime_paths["apps_root"]).exists()
