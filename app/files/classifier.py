from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.path_policy import PathPolicyError, validate_classification_target


def _resolve_classification_target(
    template: str,
    runtime_paths: dict[str, str],
) -> Path:
    try:
        target_str = template.format(**runtime_paths)
    except (KeyError, ValueError, IndexError) as exc:
        raise PathPolicyError(
            f"分类目标模板无效: {template}",
            f"Invalid classification target template: {template}",
        ) from exc
    return validate_classification_target(target_str, runtime_paths["archive_root"])


def classify_file(
    file_path: Path,
    rules_config: dict[str, Any],
    runtime_paths: dict[str, str]
) -> Path:
    suffix = file_path.suffix.lower()

    for rule in rules_config.get("rules", []):
        exts = [ext.lower() for ext in rule.get("extensions", [])]
        if suffix in exts:
            target_template = rule.get("target")
            if not target_template:
                raise PathPolicyError(
                    "分类规则缺少有效的目标路径。",
                    "The classification rule is missing a valid target path.",
                )
            return _resolve_classification_target(str(target_template), runtime_paths)

    fallback = rules_config.get("fallback_target", "{archive_root}/99-Others")
    return _resolve_classification_target(str(fallback), runtime_paths)
