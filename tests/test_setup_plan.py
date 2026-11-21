from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.core import planning
from app.core.settings import build_runtime_paths, ensure_runtime_directories, runtime_directories


def _snapshot(path: Path) -> dict:
    state = {}

    def visit(entry: Path) -> None:
        info = entry.lstat()
        state[entry.relative_to(path)] = (info.st_mode, info.st_mtime_ns)
        if entry.is_symlink() or entry.is_junction():
            state[entry.relative_to(path)] += (os.readlink(entry),)
        elif stat.S_ISDIR(info.st_mode):
            for child in entry.iterdir():
                visit(child)
        elif stat.S_ISREG(info.st_mode):
            state[entry.relative_to(path)] += (entry.read_bytes(),)

    visit(path)
    return state


@pytest.fixture
def layout(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "Managed [preview]"
    source = tmp_path / "Downloads"
    source.mkdir()
    (source / "existing.txt").write_bytes(b"leave source data alone")
    return root, source


def _preview(root: Path, source: Path, *, json_output: bool = True):
    argv = ["setup", "plan", "--root", str(root), "--source", str(source)]
    if json_output:
        argv.append("--json")
    before = _snapshot(root.parent)
    result = CliRunner().invoke(app, argv)
    assert _snapshot(root.parent) == before
    return result


def _json_preview(root: Path, source: Path) -> dict:
    result = _preview(root, source)
    plan = json.loads(result.stdout)
    assert plan["schema_version"] == 1
    assert result.exit_code == (1 if plan["status"] == "blocked" else 0)
    return plan


def _actions(plan: dict) -> dict:
    return {Path(item["path"]): item for item in plan["directories"]}


def test_empty_home_and_missing_root_stay_missing(layout, isolated_pathpilot_home):
    root, source = layout
    plan = _json_preview(root, source)
    assert plan["status"] == "ready"
    assert plan["root"] == str(root)
    assert plan["source"] == str(source)
    assert plan["blockers"] == []
    runtime = build_runtime_paths({"base_paths": {"root_dir": str(root)}})
    assert list(_actions(plan)) == [Path(target) for target in runtime_directories(runtime)]
    assert {row["action"] for row in plan["directories"]} == {"create"}
    assert all(row["verify_at_apply"] for row in plan["directories"])
    assert not isolated_pathpilot_home.exists()
    assert not root.exists()
    human = _preview(root, source, json_output=False)
    assert human.exit_code == 0
    assert "将创建" in human.stdout
    assert "应用时验证" in human.stdout
    assert "初始化预览" in human.stdout


def test_snapshot_and_existing_targets_are_preserved(layout, isolated_pathpilot_home):
    root, source = layout
    settings = isolated_pathpilot_home / "config" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        json.dumps({"base_paths": {"root_dir": str(source)}, "watch_directories": [str(root)]}),
        encoding="utf-8",
    )
    (root / "Apps").mkdir(parents=True)
    (root / "Apps" / "existing.txt").write_bytes(b"leave managed data alone")
    plan = _json_preview(root, source)
    assert plan["status"] == "ready"
    assert _actions(plan)[root / "Apps"]["action"] == "reuse"
    assert _actions(plan)[root / "Downloads"]["action"] == "create"


def test_corrupt_settings_are_reported_and_untouched(layout, isolated_pathpilot_home):
    settings = isolated_pathpilot_home / "config" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_bytes(b'{"unfinished":')
    plan = _json_preview(*layout)
    assert plan["status"] == "blocked"
    assert plan["directories"] == []
    assert plan["blockers"][0]["code"] == "settings_corrupt"


def test_file_blocks_target_and_its_descendants(layout):
    root, source = layout
    root.mkdir()
    (root / "Apps").write_bytes(b"keep this file")
    plan = _json_preview(root, source)
    assert plan["status"] == "blocked"
    assert _actions(plan)[root / "Apps"]["action"] == "blocked"
    assert _actions(plan)[root / "Apps" / "Professional" / "SDKs"]["action"] == "blocked"
    assert any(item["code"] == "file_conflict" and Path(item["path"]) == root / "Apps"
               for item in plan["blockers"])


def test_policy_blocks_overlapping_source_and_protected_root(layout, isolated_pathpilot_home):
    root, _ = layout
    source = root / "Nested"
    source.mkdir(parents=True)
    plan = _json_preview(root, source)
    assert plan["status"] == "blocked"
    assert plan["blockers"][0]["code"] == "source_policy"
    protected = _json_preview(isolated_pathpilot_home, source)
    assert protected["status"] == "blocked"
    assert protected["blockers"][0]["code"] == "root_policy"


def test_missing_or_unreadable_source_is_blocked(layout, monkeypatch):
    root, source = layout
    plan = _json_preview(root, root.parent / "missing")
    assert plan["status"] == "blocked"
    assert plan["blockers"][0]["code"] == "source_missing"
    real_scandir = os.scandir

    def deny_source(path):
        if Path(path) == source:
            raise PermissionError("Simulated source access denial")
        return real_scandir(path)

    monkeypatch.setattr(planning, "scandir", deny_source)
    plan = _json_preview(root, source)
    assert plan["status"] == "blocked"
    assert plan["blockers"][0]["code"] == "source_unavailable"


def test_directory_redirect_outside_managed_root_is_blocked(layout):
    root, source = layout
    root.mkdir()
    outside = root.parent / "External"
    outside.mkdir()
    target = root / "Downloads"
    if os.name == "nt":
        subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(target), str(outside)],
            check=True,
            capture_output=True,
        )
        assert target.is_junction()
    else:
        target.symlink_to(outside, target_is_directory=True)

    plan = _json_preview(root, source)
    assert plan["status"] == "blocked"
    assert _actions(plan)[target]["action"] == "blocked"
    assert any(item["code"] == "path_escape" and Path(item["path"]) == target
               for item in plan["blockers"])


def test_runtime_creation_uses_the_preview_layout(layout):
    root, source = layout
    plan = _json_preview(root, source)
    runtime = build_runtime_paths({"base_paths": {"root_dir": str(root)}})
    ensure_runtime_directories(runtime)
    assert all(path.is_dir() for path in _actions(plan))
    assert all(any(path == target or path in target.parents for target in _actions(plan))
               for path in root.rglob("*"))
