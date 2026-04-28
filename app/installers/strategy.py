from __future__ import annotations

from pathlib import Path
from typing import Any


def infer_target_by_filename(file_path: Path, runtime_paths: dict[str, str]) -> str:
    name = file_path.stem.lower()

    # 一个简单的启发式分类，后面可以慢慢扩展
    if any(k in name for k in ["ollama", "model", "llm", "ai"]):
        return f"{runtime_paths['apps_root']}/Professional/AI/{file_path.stem}"

    if any(k in name for k in ["idea", "pycharm", "webstorm", "clion", "vscode"]):
        return f"{runtime_paths['apps_root']}/Professional/IDEs/{file_path.stem}"

    if any(k in name for k in ["python", "jdk", "java", "node", "git", "maven", "gradle"]):
        return f"{runtime_paths['apps_root']}/Professional/SDKs/{file_path.stem}"

    if any(k in name for k in ["docker", "nacos", "seata", "redis", "mysql"]):
        return f"{runtime_paths['apps_root']}/Professional/DevOps/{file_path.stem}"

    return f"{runtime_paths['apps_root']}/General/Utilities/{file_path.stem}"


def build_suggestion_from_known_app(
    file_path: Path,
    known_rule: dict[str, Any],
    runtime_paths: dict[str, str]
) -> dict[str, Any]:
    installer = str(file_path.resolve()).replace("\\", "/")
    target = known_rule["target"].format(**runtime_paths)
    command = known_rule["command_template"].format(
        installer=installer,
        target=target,
        **runtime_paths
    )

    return {
        "name": known_rule["name"],
        "source": "known_app",
        "family": known_rule.get("family", "unknown"),
        "mode": known_rule.get("mode", "suggest"),
        "installer": installer,
        "target": target,
        "command": command
    }


def build_suggestion_from_family(
    file_path: Path,
    family_rule: dict[str, Any],
    runtime_paths: dict[str, str]
) -> dict[str, Any]:
    installer = str(file_path.resolve()).replace("\\", "/")
    target = infer_target_by_filename(file_path, runtime_paths)
    command = family_rule["command_template"].format(
        installer=installer,
        target=target,
        **runtime_paths
    )

    return {
        "name": file_path.stem,
        "source": "family",
        "family": family_rule["family"],
        "mode": family_rule.get("mode", "suggest"),
        "installer": installer,
        "target": target,
        "command": command
    }
