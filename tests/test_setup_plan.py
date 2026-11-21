from __future__ import annotations

import ctypes
import json
import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.core import planning, windows_discovery
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


def _discover(tmp_path: Path, *options: str, json_output: bool = True):
    argv = ["setup", "plan", *options]
    if json_output:
        argv.append("--json")
    before = _snapshot(tmp_path)
    result = CliRunner().invoke(app, argv)
    assert _snapshot(tmp_path) == before
    if not json_output:
        return result
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 1
    assert result.exit_code == (1 if payload["status"] == "blocked" else 0)
    return payload


@pytest.fixture
def discovery_host(tmp_path, monkeypatch, isolated_pathpilot_home):
    profile = tmp_path / "Profile"
    downloads = tmp_path / "Redirected Downloads"
    downloads.mkdir()
    profile.mkdir()
    settings = isolated_pathpilot_home / "config/settings.json"
    monkeypatch.delenv("PATHPILOT_HOME")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: profile))
    monkeypatch.setattr(planning, "get_settings_path", lambda: settings)
    monkeypatch.setattr(planning, "known_downloads", lambda: downloads)
    monkeypatch.setattr(planning, "fixed_drive_candidates", lambda: [])
    return profile, downloads, settings


@pytest.mark.parametrize("override", ["none", "root", "source", "both"])
def test_discovery_supports_all_override_combinations(tmp_path, discovery_host, override):
    profile, downloads, _ = discovery_host
    root = tmp_path / "Custom"
    source = tmp_path / "Source"
    source.mkdir()
    options = []
    if override in {"root", "both"}:
        options.extend(["--root", str(root)])
    if override in {"source", "both"}:
        options.extend(["--source", str(source)])

    plan = _discover(tmp_path, *options)
    assert plan["status"] == "ready"
    assert len(plan["directories"]) == 22
    assert plan["root"] == str(root if "--root" in options else profile / "PathPilot")
    assert plan["source"] == str(source if "--source" in options else downloads)
    assert plan["root_origin"] == ("cli" if "--root" in options else "profile")
    assert plan["source_origin"] == ("cli" if "--source" in options else "known_folder")
    assert plan["root_reason"] and plan["source_reason"]
    if not options:
        human = _discover(tmp_path, json_output=False)
        assert human.exit_code == 0
        assert "Windows Downloads Known Folder" in human.stdout


def test_saved_paths_precede_discovery_and_internal_incoming_is_excluded(tmp_path, discovery_host, monkeypatch):
    _, source, settings = discovery_host
    managed = tmp_path / "Saved Root"
    incoming = managed / "Downloads" / "00-Incoming"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({
        "base_paths": {"root_dir": str(managed)},
        "watch_directories": [str(incoming), "{incoming_root}", str(source)],
    }), encoding="utf-8")

    def unexpected_probe():
        pytest.fail("Saved or explicit paths should bypass native discovery.")

    monkeypatch.setattr(planning, "known_downloads", unexpected_probe)
    monkeypatch.setattr(planning, "fixed_drive_candidates", unexpected_probe)
    plan = _discover(tmp_path)
    assert (plan["status"], plan["root_origin"], plan["source_origin"]) == ("ready", "config", "config")
    assert Path(plan["root"]) == managed
    assert Path(plan["source"]) == source
    overridden = _discover(tmp_path, "--root", str(tmp_path / "Explicit"))
    assert (overridden["status"], overridden["root_origin"], overridden["source_origin"]) == ("ready", "cli", "config")


def test_multiple_external_sources_block_until_explicit_override(tmp_path, discovery_host):
    _, source, settings = discovery_host
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({
        "watch_directories": ["{user_downloads}", str(tmp_path / "Other"), "{incoming_root}"],
    }), encoding="utf-8")
    plan = _discover(tmp_path)
    assert plan["status"] == "blocked"
    assert "2 external sources" in plan["blockers"][0]["reason"]
    assert _discover(tmp_path, "--source", str(source))["status"] == "ready"


def test_known_folder_failure_is_actionable_and_cli_source_bypasses_it(tmp_path, discovery_host, monkeypatch):
    _, source, _ = discovery_host

    def failed_query():
        raise OSError("Simulated Known Folder failure")

    monkeypatch.setattr(planning, "known_downloads", failed_query)
    failed = _discover(tmp_path)
    assert failed["status"] == "blocked"
    assert failed["source"] == ""
    assert failed["blockers"][0]["code"] == "downloads_discovery"
    assert "--source" in failed["blockers"][0]["reason"]
    assert _discover(tmp_path, "--source", str(source))["status"] == "ready"


def test_invalid_explicit_paths_and_profile_overlap_remain_blocked(tmp_path, discovery_host):
    profile, _, _ = discovery_host
    missing = tmp_path / "Missing Source"
    plan = _discover(tmp_path, "--source", str(missing))
    assert (plan["status"], plan["source_origin"], plan["source"]) == ("blocked", "cli", str(missing))
    assert plan["blockers"][0]["code"] == "source_missing"
    occupied = tmp_path / "Occupied"
    occupied.write_bytes(b"existing data")
    plan = _discover(tmp_path, "--root", str(occupied))
    assert (plan["status"], plan["root_origin"], plan["root"]) == ("blocked", "cli", str(occupied))
    assert any(item["code"] == "file_conflict" for item in plan["blockers"])
    plan = _discover(tmp_path, "--source", str(profile))
    assert plan["status"] == "blocked"
    assert any(item["code"] == "source_policy" for item in plan["blockers"])


def test_automatic_root_tries_next_safe_fixed_drive(tmp_path, discovery_host, monkeypatch):
    _, source, _ = discovery_host
    conflicting = source
    suitable = tmp_path / "Fixed Drive"
    suitable.mkdir()
    monkeypatch.setattr(planning, "fixed_drive_candidates", lambda: [
        (str(conflicting), 2000), (str(suitable), 1000),
    ])
    plan = _discover(tmp_path)
    assert plan["status"] == "ready"
    assert plan["root"] == str(suitable / "PathPilot")
    assert plan["root_origin"] == "fixed_drive"
    assert "1000 free bytes" in plan["root_reason"]


def test_other_candidate_incoming_is_not_silently_removed_from_config(tmp_path, discovery_host, monkeypatch):
    _, source, settings = discovery_host
    other_drive = tmp_path / "Other Drive"
    other_source = other_drive / "PathPilot" / "Downloads" / "00-Incoming"
    other_source.mkdir(parents=True)
    preferred = tmp_path / "Preferred"
    preferred.mkdir()
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"watch_directories": [str(source), str(other_source)]}), encoding="utf-8")
    monkeypatch.setattr(planning, "fixed_drive_candidates", lambda: [
        (str(preferred), 2000), (str(other_drive), 1000),
    ])
    plan = _discover(tmp_path)
    assert plan["status"] == "blocked"
    assert "2 external sources" in plan["blockers"][0]["reason"]


def test_auto_isolation_never_probes_host_and_writes_nothing(tmp_path, isolated_pathpilot_home, monkeypatch):
    runtime = isolated_pathpilot_home.with_name(isolated_pathpilot_home.name + "-runtime")
    source = runtime / "user-home" / "Downloads"

    def unexpected_probe():
        pytest.fail("PATHPILOT_HOME must bypass native discovery.")

    monkeypatch.setattr(planning, "known_downloads", unexpected_probe)
    monkeypatch.setattr(planning, "fixed_drive_candidates", unexpected_probe)
    failed = _discover(tmp_path)
    assert failed["status"] == "blocked"
    assert failed["blockers"][0]["code"] == "source_missing"
    assert not runtime.exists()
    source.mkdir(parents=True)
    plan = _discover(tmp_path)
    assert (plan["status"], plan["root_origin"], plan["source_origin"]) == ("ready", "isolated", "isolated")
    assert plan["root"] == str(runtime / "managed")
    assert plan["source"] == str(source)
    assert not isolated_pathpilot_home.exists()


def test_corrupt_state_blocks_before_automatic_discovery(tmp_path, discovery_host, monkeypatch):
    _, _, settings = discovery_host
    settings.parent.mkdir(parents=True)
    settings.write_bytes(b"{")

    def unexpected_probe():
        pytest.fail("Corrupt state should block before discovery.")

    monkeypatch.setattr(planning, "fixed_drive_candidates", unexpected_probe)
    plan = _discover(tmp_path)
    assert plan["status"] == "blocked"
    assert plan["blockers"][0]["code"] == "settings_corrupt"


def test_fixed_drive_discovery_filters_and_orders_verified_volumes(monkeypatch):
    mounts = ["Z:\\", "F:\\", "D:\\", "E:\\", "G:\\", "X:\\", "Y:\\", "H:\\mount"]
    types = dict(zip(mounts, [3, 3, 3, 3, 2, 4, 5, 3]))
    queried = []

    def available(root):
        queried.append(root)
        if root == "F:\\":
            raise PermissionError("Inaccessible fixed volume")
        return 100

    monkeypatch.setattr(windows_discovery, "_system_drive", lambda: "Z:")
    monkeypatch.setattr(windows_discovery.psutil, "disk_partitions",
                        lambda **_: [SimpleNamespace(mountpoint=mount) for mount in mounts])
    monkeypatch.setattr(windows_discovery, "_drive_type", types.__getitem__)
    monkeypatch.setattr(windows_discovery, "_available_bytes", available)
    assert windows_discovery.fixed_drive_candidates() == [("D:\\", 100), ("E:\\", 100)]
    assert queried == ["F:\\", "D:\\", "E:\\"]


def test_known_folder_adapter_passes_current_user_and_frees_result(monkeypatch):
    redirected = r"\\fileserver\users\Alice\Downloads"
    buffer = ctypes.create_unicode_buffer(redirected)
    freed = []

    def get_path(folder_id, flags, token, result):
        assert ctypes.string_at(folder_id, 16).hex() == "90e24d373f126545916439c4925e467b"
        assert flags == 0x4000
        assert token is None
        ctypes.cast(result, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.addressof(buffer)
        return 0

    def free(pointer):
        freed.append(pointer.value)

    dlls = {
        "shell32": SimpleNamespace(SHGetKnownFolderPath=get_path),
        "ole32": SimpleNamespace(CoTaskMemFree=free),
    }
    monkeypatch.setattr(windows_discovery, "_windows_dll", dlls.__getitem__)
    assert windows_discovery.known_downloads() == Path(redirected)
    assert freed == [ctypes.addressof(buffer)]
