from __future__ import annotations

from pathlib import Path
from typing import Any


def classify_file(
    file_path: Path,
    rules_config: dict[str, Any],
    runtime_paths: dict[str, str]
) -> Path:
    suffix = file_path.suffix.lower()

    for rule in rules_config.get("rules", []):
        exts = [ext.lower() for ext in rule.get("extensions", [])]
        if suffix in exts:
            target_template = rule["target"]
            target_str = target_template.format(**runtime_paths)
            return Path(target_str)

    fallback = rules_config.get("fallback_target", "{archive_root}/99-Others")
    return Path(fallback.format(**runtime_paths))
