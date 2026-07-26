from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


APP_HOME = Path(os.environ.get("PATHPILOT_HOME", Path.home() / ".pathpilot")).resolve()
CONFIG_DIR = APP_HOME / "config"
DATA_DIR = APP_HOME / "data"
LOG_DIR = DATA_DIR / "logs"


DEFAULT_SETTINGS: dict[str, Any] = {
    "watch_directories": [
        "{user_downloads}"
    ],
    "base_paths": {
        "root_dir": ""
    },
    "behavior": {
        "ignore_hidden_files": True,
        "stable_check_seconds": 2,
        "stable_checks": 3,
        "create_missing_dirs": True,
        "overwrite_strategy": "rename"
    }
}


DEFAULT_RULES: dict[str, Any] = {
    "rules": [
        {
            "name": "Installers",
            "extensions": [".exe", ".msi"],
            "target": "{archive_root}/01-Software/_IncomingInstallers"
        },
        {
            "name": "Archives",
            "extensions": [".zip", ".7z", ".rar"],
            "target": "{archive_root}/07-Archives/_IncomingArchives"
        },
        {
            "name": "Images",
            "extensions": [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"],
            "target": "{archive_root}/03-Media/Images"
        },
        {
            "name": "Videos",
            "extensions": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"],
            "target": "{archive_root}/03-Media/Videos"
        },
        {
            "name": "Documents",
            "extensions": [".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".txt"],
            "target": "{archive_root}/05-Documents/Mixed"
        },
        {
            "name": "PythonCode",
            "extensions": [".py", ".ipynb"],
            "target": "{archive_root}/06-Code/Python"
        },
        {
            "name": "JavaCode",
            "extensions": [".java", ".jar"],
            "target": "{archive_root}/06-Code/Java"
        }
    ],
    "fallback_target": "{archive_root}/99-Others"
}


DEFAULT_INSTALLER_RULES: dict[str, Any] = {
    "known_apps": [
        {
            "name": "Ollama",
            "match": {
                "filename_contains": ["ollama"]
            },
            "target": "{apps_root}/Professional/AI/Ollama",
            "family": "inno_setup",
            "mode": "suggest"
        }
    ],
    "installer_families": [
        {
            "family": "inno_setup",
            "mode": "suggest"
        },
        {
            "family": "nsis",
            "mode": "suggest"
        },
        {
            "family": "msi",
            "mode": "suggest"
        },
        {
            "family": "unknown",
            "mode": "suggest"
        }
    ]
}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def deep_merge(default: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(default)

    for key, value in current.items():
        if (
            isinstance(value, dict)
            and isinstance(result.get(key), dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def read_json_or_default(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return deepcopy(default)

    if data in ({}, [], None):
        return deepcopy(default)

    if isinstance(default, dict) and isinstance(data, dict):
        return deep_merge(default, data)

    return data


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_json_file(path: Path, default: Any) -> None:
    data = read_json_or_default(path, default)
    write_json(path, data)


def ensure_user_config_files() -> None:
    ensure_dir(CONFIG_DIR)
    ensure_dir(DATA_DIR)
    ensure_dir(LOG_DIR)

    ensure_json_file(CONFIG_DIR / "settings.json", DEFAULT_SETTINGS)
    ensure_json_file(CONFIG_DIR / "rules.json", DEFAULT_RULES)
    ensure_json_file(CONFIG_DIR / "installer_rules.json", DEFAULT_INSTALLER_RULES)
    ensure_json_file(DATA_DIR / "pending_installs.json", [])


def get_settings_path() -> Path:
    ensure_user_config_files()
    return CONFIG_DIR / "settings.json"


def get_rules_path() -> Path:
    ensure_user_config_files()
    return CONFIG_DIR / "rules.json"


def get_installer_rules_path() -> Path:
    ensure_user_config_files()
    return CONFIG_DIR / "installer_rules.json"


def get_pending_installs_path() -> Path:
    ensure_user_config_files()
    return DATA_DIR / "pending_installs.json"
