from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from app.core.path_policy import PathPolicyError, normalize_path
from app.files.classifier import classify_file
from app.files.watcher import DownloadEventHandler


def _settings(runtime_paths: dict[str, str], rules: dict) -> tuple[dict, dict]:
    settings = {
        "runtime_paths": runtime_paths,
        "behavior": {
            "ignore_hidden_files": True,
            "stable_check_seconds": 0,
            "stable_checks": 1,
            "create_missing_dirs": True,
            "overwrite_strategy": "rename",
        },
    }
    return settings, rules


def _incoming_file(runtime_paths: dict[str, str], name: str, content: str = "fixture") -> Path:
    incoming = Path(runtime_paths["incoming_root"])
    incoming.mkdir(parents=True, exist_ok=True)
    path = incoming / name
    path.write_text(content, encoding="utf-8")
    return path


def _other_fixed_drive(current: Path) -> Path | None:
    current_drive = current.resolve().drive.upper()
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        candidate = Path(f"{letter}:\\")
        try:
            if candidate.exists() and candidate.drive.upper() != current_drive:
                return candidate
        except OSError:
            continue
    return None


def test_default_document_rule_stays_inside_archive(
    tmp_path: Path, runtime_paths: dict[str, str]
) -> None:
    source = _incoming_file(runtime_paths, "notes.txt")
    rules = {
        "rules": [
            {
                "name": "Documents",
                "extensions": [".txt"],
                "target": "{archive_root}/05-Documents/Mixed",
            }
        ]
    }
    target = classify_file(source, rules, runtime_paths)
    assert target == normalize_path(Path(runtime_paths["archive_root"]) / "05-Documents" / "Mixed")
    assert target.is_relative_to(normalize_path(runtime_paths["archive_root"]))
    assert target != normalize_path(runtime_paths["archive_root"])


def test_classify_rejects_parent_traversal(
    runtime_paths: dict[str, str],
) -> None:
    source = _incoming_file(runtime_paths, "escape.txt")
    rules = {
        "rules": [
            {
                "name": "escape",
                "extensions": [".txt"],
                "target": "{archive_root}/../../outside-managed",
            }
        ]
    }
    with pytest.raises(PathPolicyError):
        classify_file(source, rules, runtime_paths)
    assert source.exists()


def test_classify_rejects_absolute_path_outside_archive(
    tmp_path: Path, runtime_paths: dict[str, str]
) -> None:
    source = _incoming_file(runtime_paths, "absolute.txt")
    outside = tmp_path / "outside-managed" / "abs-dest"
    rules = {
        "rules": [
            {
                "name": "absolute",
                "extensions": [".txt"],
                "target": str(outside),
            }
        ]
    }
    with pytest.raises(PathPolicyError):
        classify_file(source, rules, runtime_paths)
    assert source.exists()
    assert not outside.exists()


def test_classify_rejects_other_drive_letter(runtime_paths: dict[str, str]) -> None:
    other = _other_fixed_drive(Path(runtime_paths["archive_root"]))
    if other is None:
        pytest.skip("No second fixed drive is available for this test.")

    source = _incoming_file(runtime_paths, "otherdrive.txt")
    dest_root = Path(tempfile.mkdtemp(prefix="pathpilot-i2-drive-", dir=str(other)))
    try:
        target = dest_root / "dest"
        rules = {
            "rules": [
                {
                    "name": "drive",
                    "extensions": [".txt"],
                    "target": str(target),
                }
            ]
        }
        with pytest.raises(PathPolicyError):
            classify_file(source, rules, runtime_paths)
        assert source.exists()
        assert not target.exists()
    finally:
        shutil.rmtree(dest_root, ignore_errors=True)


def test_fallback_target_is_also_constrained(runtime_paths: dict[str, str]) -> None:
    source = _incoming_file(runtime_paths, "unknown.bin")
    rules = {"rules": [], "fallback_target": "{archive_root}/../escaped-fallback"}
    with pytest.raises(PathPolicyError):
        classify_file(source, rules, runtime_paths)
    assert source.exists()


def test_invalid_template_is_rejected(runtime_paths: dict[str, str]) -> None:
    source = _incoming_file(runtime_paths, "template.txt")
    rules = {
        "rules": [
            {
                "name": "bad-template",
                "extensions": [".txt"],
                "target": "{not_a_runtime_path}/docs",
            }
        ]
    }
    with pytest.raises(PathPolicyError):
        classify_file(source, rules, runtime_paths)
    assert source.exists()


def test_watcher_does_not_move_file_for_escaping_rule(
    runtime_paths: dict[str, str],
) -> None:
    source = _incoming_file(runtime_paths, "watched.txt")
    outside = Path(runtime_paths["root_dir"]).parent / "outside-managed" / "watched.txt"
    rules = {
        "rules": [
            {
                "name": "escape",
                "extensions": [".txt"],
                "target": "{archive_root}/../../outside-managed",
            }
        ]
    }
    settings, rules = _settings(runtime_paths, rules)
    DownloadEventHandler(settings, rules)._handle_file(source)
    assert source.exists()
    assert not outside.exists()


def _make_directory_junction(link: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    completed = os.system(f'cmd /c mklink /J "{link}" "{destination}"')
    if completed != 0 or not link.exists():
        pytest.skip("Unable to create a Windows directory junction in this environment.")


def _make_directory_symlink(link: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(destination, link, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Unable to create a directory symbolic link: {exc}")
    if not link.exists():
        pytest.skip("Directory symbolic link was not created.")


@pytest.mark.skipif(os.name != "nt", reason="Windows junction test")
def test_classify_rejects_junction_escaping_archive(
    tmp_path: Path, runtime_paths: dict[str, str]
) -> None:
    source = _incoming_file(runtime_paths, "junction.txt")
    outside = tmp_path / "junction-dest"
    junction = Path(runtime_paths["archive_root"]) / "99-Link"
    Path(runtime_paths["archive_root"]).mkdir(parents=True, exist_ok=True)
    _make_directory_junction(junction, outside)
    rules = {
        "rules": [
            {
                "name": "junction",
                "extensions": [".txt"],
                "target": str(junction),
            }
        ]
    }
    with pytest.raises(PathPolicyError):
        classify_file(source, rules, runtime_paths)
    assert source.exists()
    assert source.parent == Path(runtime_paths["incoming_root"])
    assert list(outside.iterdir()) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows junction test")
def test_watcher_does_not_follow_escaping_junction(
    tmp_path: Path, runtime_paths: dict[str, str]
) -> None:
    source = _incoming_file(runtime_paths, "junction-watch.txt")
    outside = tmp_path / "junction-watch-dest"
    junction = Path(runtime_paths["archive_root"]) / "99-Link"
    Path(runtime_paths["archive_root"]).mkdir(parents=True, exist_ok=True)
    _make_directory_junction(junction, outside)
    rules = {
        "rules": [
            {
                "name": "junction",
                "extensions": [".txt"],
                "target": str(junction),
            }
        ]
    }
    settings, rules = _settings(runtime_paths, rules)
    DownloadEventHandler(settings, rules)._handle_file(source)
    assert source.exists()
    assert list(outside.iterdir()) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows symlink test")
def test_classify_rejects_symlink_escaping_archive(
    tmp_path: Path, runtime_paths: dict[str, str]
) -> None:
    source = _incoming_file(runtime_paths, "symlink.txt")
    outside = tmp_path / "symlink-dest"
    link = Path(runtime_paths["archive_root"]) / "99-Symlink"
    Path(runtime_paths["archive_root"]).mkdir(parents=True, exist_ok=True)
    _make_directory_symlink(link, outside)
    rules = {
        "rules": [
            {
                "name": "symlink",
                "extensions": [".txt"],
                "target": str(link),
            }
        ]
    }
    with pytest.raises(PathPolicyError):
        classify_file(source, rules, runtime_paths)
    assert source.exists()
    assert list(outside.iterdir()) == []


def test_watcher_still_classifies_valid_target(runtime_paths: dict[str, str]) -> None:
    source = _incoming_file(runtime_paths, "keep.txt")
    rules = {
        "rules": [
            {
                "name": "Documents",
                "extensions": [".txt"],
                "target": "{archive_root}/05-Documents/Mixed",
            }
        ]
    }
    settings, rules = _settings(runtime_paths, rules)
    DownloadEventHandler(settings, rules)._handle_file(source)
    final = Path(runtime_paths["archive_root"]) / "05-Documents" / "Mixed" / "keep.txt"
    assert final.exists()
    assert not source.exists()
