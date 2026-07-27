from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from app.core.path_policy import normalize_path, validate_install_target


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


def build_execution_fields(
    installer_path: str | Path,
    target_dir: str | Path,
    installer_family: str,
) -> dict[str, Any]:
    installer = str(normalize_path(installer_path))
    target = str(normalize_path(target_dir))

    if installer_family == "msi":
        executable = str(
            normalize_path(
                Path(os.environ.get("SystemRoot", r"C:\Windows"))
                / "System32"
                / "msiexec.exe"
            )
        )
        args = ["/i", installer]
    elif installer_family == "inno_setup":
        executable = installer
        args = [f"/DIR={target}"]
    elif installer_family == "nsis":
        executable = installer
        args = [f"/D={target}"]
    else:
        executable = installer
        args = []

    argv = [executable, *args]
    return {
        "executable": executable,
        "args": args,
        "preview": subprocess.list2cmdline(argv),
        "installer_path": installer,
        "target_dir": target,
        "installer_family": installer_family,
    }


def rebuild_execution_fields(record: dict[str, Any], target_dir: str | Path) -> dict[str, Any]:
    return build_execution_fields(
        installer_path=record["installer_path"],
        target_dir=target_dir,
        installer_family=record["installer_family"],
    )


def build_suggestion_from_known_app(
    file_path: Path,
    known_rule: dict[str, Any],
    runtime_paths: dict[str, str]
) -> dict[str, Any]:
    target = validate_install_target(
        known_rule["target"].format(**runtime_paths),
        runtime_paths["apps_root"],
    )
    family = known_rule.get("family", "unknown")

    return {
        "name": known_rule["name"],
        "source": "known_app",
        "mode": "suggest",
        **build_execution_fields(file_path, target, family),
    }


def build_suggestion_from_family(
    file_path: Path,
    family_rule: dict[str, Any],
    runtime_paths: dict[str, str]
) -> dict[str, Any]:
    target = validate_install_target(
        infer_target_by_filename(file_path, runtime_paths),
        runtime_paths["apps_root"],
    )
    family = family_rule["family"]

    return {
        "name": file_path.stem,
        "source": "family",
        "mode": "suggest",
        **build_execution_fields(file_path, target, family),
    }
