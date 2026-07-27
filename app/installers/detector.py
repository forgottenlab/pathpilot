from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.json_store import ensure_json_file, read_json
from app.core.paths import DEFAULT_INSTALLER_RULES, get_installer_rules_path


def load_installer_rules() -> dict[str, Any]:
    path = get_installer_rules_path()
    ensure_json_file(path, DEFAULT_INSTALLER_RULES, expected_type=dict)

    data = read_json(path, expected_type=dict)

    data.setdefault("known_apps", [])
    data.setdefault("installer_families", [])
    for rule in [*data["known_apps"], *data["installer_families"]]:
        if isinstance(rule, dict):
            rule["mode"] = "suggest"
    return data


def match_known_app(file_path: Path, installer_rules: dict[str, Any]) -> dict[str, Any] | None:
    filename_lower = file_path.name.lower()

    for rule in installer_rules.get("known_apps", []):
        match = rule.get("match", {})
        filename_contains = [item.lower() for item in match.get("filename_contains", [])]

        if filename_contains and any(keyword in filename_lower for keyword in filename_contains):
            return rule

    return None


def detect_installer_family(file_path: Path) -> str:
    suffix = file_path.suffix.lower()

    if suffix == ".msi":
        return "msi"

    if suffix != ".exe":
        return "unknown"

    try:
        with file_path.open("rb") as f:
            data = f.read(1024 * 1024)
            text = data.decode("latin1", errors="ignore").lower()

        if "inno setup" in text:
            return "inno_setup"

        if "nullsoft" in text or "nsis" in text:
            return "nsis"

    except Exception:
        pass

    return "unknown"


def get_family_rule(family: str, installer_rules: dict[str, Any]) -> dict[str, Any] | None:
    for rule in installer_rules.get("installer_families", []):
        if rule.get("family") == family:
            return rule
    return None
