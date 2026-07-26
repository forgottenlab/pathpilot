from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psutil

from app.core.path_policy import normalize_path, validate_runtime_layout
from app.core.json_store import ensure_json_file, read_json, read_json_snapshot
from app.core.paths import (
    DEFAULT_RULES,
    DEFAULT_SETTINGS,
    get_config_dir,
)


JSON_DEFAULTS = {
    "settings.json": DEFAULT_SETTINGS,
    "rules.json": DEFAULT_RULES,
}


def load_json(
    filename: str,
    *,
    create_missing: bool = True,
    readonly: bool = False,
) -> dict[str, Any]:
    path = get_config_dir() / filename
    if create_missing:
        ensure_json_file(path, JSON_DEFAULTS[filename], expected_type=dict)
    loader = read_json_snapshot if readonly else read_json
    return loader(path, expected_type=dict)


def is_fixed_drive(partition: psutil._common.sdiskpart) -> bool:
    opts = (partition.opts or "").lower()
    device = (partition.device or "").lower()

    if "cdrom" in opts:
        return False
    if "removable" in opts:
        return False
    if not device.endswith("\\"):
        return False
    return True


def get_system_drive() -> str:
    system_drive = os.environ.get("SystemDrive", "C:")
    return system_drive.rstrip("\\/").upper()


def detect_best_root_dir() -> tuple[str, list[tuple[str, int]], str]:
    system_drive = get_system_drive()
    candidates: list[tuple[str, int]] = []

    for partition in psutil.disk_partitions(all=False):
        try:
            if not is_fixed_drive(partition):
                continue

            mountpoint = partition.mountpoint.rstrip("\\/")
            drive_letter = mountpoint.upper()
            usage = psutil.disk_usage(partition.mountpoint)

            if drive_letter != system_drive:
                candidates.append((drive_letter, usage.free))
        except Exception:
            continue

    if candidates:
        best_drive = max(candidates, key=lambda x: x[1])[0]
        return f"{best_drive}/PathPilot".replace("\\", "/"), candidates, system_drive

    return f"{system_drive}/PathPilot".replace("\\", "/"), candidates, system_drive


def build_runtime_paths(settings: dict[str, Any]) -> dict[str, Any]:
    base_paths = settings.setdefault("base_paths", {})
    isolated_home_value = os.environ.get("PATHPILOT_HOME")
    isolated_runtime = None
    if isolated_home_value:
        state_home = Path(isolated_home_value).resolve()
        isolated_runtime = state_home.with_name(f"{state_home.name}-runtime")

    configured_root_dir = (base_paths.get("root_dir") or "").strip()
    if configured_root_dir:
        root_dir = configured_root_dir.replace("\\", "/")
        candidates: list[tuple[str, int]] = []
        system_drive = get_system_drive()
        root_selection_reason = "custom"
    elif isolated_runtime is not None:
        root_dir = str(isolated_runtime / "managed").replace("\\", "/")
        candidates = []
        system_drive = get_system_drive()
        root_selection_reason = "isolated"
    else:
        root_dir, candidates, system_drive = detect_best_root_dir()
        if candidates:
            root_selection_reason = "non_system"
        else:
            root_selection_reason = "system_fallback"

    archive_root = f"{root_dir}/Downloads"
    apps_root = f"{root_dir}/Apps"
    data_root = f"{root_dir}/Data"
    incoming_root = f"{archive_root}/00-Incoming"

    effective_user_home = (
        isolated_runtime / "user-home"
        if isolated_runtime is not None
        else Path.home()
    )
    return {
        "user_home": str(effective_user_home).replace("\\", "/"),
        "user_downloads": str((effective_user_home / "Downloads")).replace("\\", "/"),
        "root_dir": root_dir,
        "archive_root": archive_root,
        "apps_root": apps_root,
        "data_root": data_root,
        "incoming_root": incoming_root,
        "system_drive": system_drive.replace("\\", "/"),
        "root_selection_reason": root_selection_reason,
        "_disk_candidates": [
            {"drive": drive, "free_bytes": free_bytes}
            for drive, free_bytes in candidates
        ],
    }


def resolve_template(value: str, variables: dict[str, Any]) -> str:
    return value.format(**variables)


def ensure_runtime_directories(runtime_paths: dict[str, Any]) -> None:
    required_dirs = [
        runtime_paths["root_dir"],
        runtime_paths["archive_root"],
        runtime_paths["apps_root"],
        runtime_paths["data_root"],

        runtime_paths["incoming_root"],
        f"{runtime_paths['archive_root']}/01-Software/_IncomingInstallers",
        f"{runtime_paths['archive_root']}/03-Media/Images",
        f"{runtime_paths['archive_root']}/03-Media/Videos",
        f"{runtime_paths['archive_root']}/05-Documents/Mixed",
        f"{runtime_paths['archive_root']}/06-Code/Python",
        f"{runtime_paths['archive_root']}/06-Code/Java",
        f"{runtime_paths['archive_root']}/07-Archives/_IncomingArchives",
        f"{runtime_paths['archive_root']}/99-Others",

        f"{runtime_paths['apps_root']}/General/Utilities",
        f"{runtime_paths['apps_root']}/General/Communication",
        f"{runtime_paths['apps_root']}/General/Others",
        f"{runtime_paths['apps_root']}/Professional/AI",
        f"{runtime_paths['apps_root']}/Professional/IDEs",
        f"{runtime_paths['apps_root']}/Professional/SDKs",
        f"{runtime_paths['apps_root']}/Professional/DevOps",
        f"{runtime_paths['apps_root']}/Professional/Others",

        f"{runtime_paths['data_root']}/Logs",
    ]

    for dir_str in required_dirs:
        Path(dir_str).mkdir(parents=True, exist_ok=True)


def load_settings(
    *,
    create_missing: bool = True,
    create_runtime_dirs: bool = True,
    readonly: bool = False,
) -> dict[str, Any]:
    settings = load_json(
        "settings.json",
        create_missing=create_missing,
        readonly=readonly,
    )

    settings.setdefault("watch_directories", ["{user_downloads}"])
    settings.setdefault("base_paths", {})
    settings["base_paths"].setdefault("root_dir", "")

    behavior = settings.setdefault("behavior", {})
    behavior.setdefault("ignore_hidden_files", True)
    behavior.setdefault("stable_check_seconds", 2)
    behavior.setdefault("stable_checks", 3)
    behavior.setdefault("create_missing_dirs", True)
    behavior.setdefault("overwrite_strategy", "rename")

    runtime_paths = build_runtime_paths(settings)
    resolved_external_sources = validate_runtime_layout(settings, runtime_paths)
    for key in ("root_dir", "archive_root", "apps_root", "data_root", "incoming_root"):
        runtime_paths[key] = str(normalize_path(runtime_paths[key])).replace("\\", "/")
    settings["runtime_paths"] = runtime_paths

    resolved_watch_dirs = [
        str(path).replace("\\", "/")
        for path in resolved_external_sources
    ]

    incoming_root = runtime_paths["incoming_root"]
    if incoming_root not in resolved_watch_dirs:
        resolved_watch_dirs.append(incoming_root)

    settings["watch_directories"] = resolved_watch_dirs

    if create_runtime_dirs:
        ensure_runtime_directories(runtime_paths)
    return settings


def load_rules(*, create_missing: bool = True, readonly: bool = False) -> dict[str, Any]:
    rules = load_json("rules.json", create_missing=create_missing, readonly=readonly)
    rules.setdefault("rules", [])
    rules.setdefault("fallback_target", "{archive_root}/99-Others")
    return rules
