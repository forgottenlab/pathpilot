from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import psutil

from app.core.paths import CONFIG_DIR, ensure_user_config_files


def load_json(filename: str) -> dict[str, Any]:
    ensure_user_config_files()
    path = CONFIG_DIR / filename

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        return {}

    return data


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

    configured_root_dir = (base_paths.get("root_dir") or "").strip()
    if configured_root_dir:
        root_dir = configured_root_dir.replace("\\", "/")
        candidates: list[tuple[str, int]] = []
        system_drive = get_system_drive()
        root_selection_reason = "使用用户自定义根目录"
    else:
        root_dir, candidates, system_drive = detect_best_root_dir()
        if candidates:
            root_selection_reason = "自动选择非系统盘中剩余空间最大的盘"
        else:
            root_selection_reason = "未找到合适的非系统盘，退回系统盘"

    archive_root = f"{root_dir}/Downloads"
    apps_root = f"{root_dir}/Apps"
    data_root = f"{root_dir}/Data"
    incoming_root = f"{archive_root}/00-Incoming"

    return {
        "user_home": str(Path.home()).replace("\\", "/"),
        "user_downloads": str((Path.home() / "Downloads")).replace("\\", "/"),
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


def load_settings() -> dict[str, Any]:
    settings = load_json("settings.json")

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
    settings["runtime_paths"] = runtime_paths

    configured_watch_dirs = settings.get("watch_directories", ["{user_downloads}"])
    resolved_watch_dirs = [
        resolve_template(path, runtime_paths).replace("\\", "/")
        for path in configured_watch_dirs
    ]

    incoming_root = runtime_paths["incoming_root"]
    if incoming_root not in resolved_watch_dirs:
        resolved_watch_dirs.append(incoming_root)

    settings["watch_directories"] = resolved_watch_dirs

    ensure_runtime_directories(runtime_paths)
    return settings


def load_rules() -> dict[str, Any]:
    rules = load_json("rules.json")
    rules.setdefault("rules", [])
    rules.setdefault("fallback_target", "{archive_root}/99-Others")
    return rules
