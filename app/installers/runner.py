from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from app.core.logger import log
from app.core.i18n import text
from app.core.json_store import JsonStoreError
from app.core.path_policy import PathPolicyError, validate_installer_path, validate_install_target
from app.installers.queue import claim_install_suggestion, finish_install_claim, prepare_install_launch
from app.installers.strategy import rebuild_execution_fields


def log_install_suggestion(record: dict[str, Any]) -> None:
    log("=" * 60)
    log(text(f"已生成安装建议 #{record['id']}", f"Created install suggestion #{record['id']}"))
    log(text(f"名称: {record['name']}", f"Name: {record['name']}"))
    log(text(f"来源类型: {record['source']}", f"Source: {record['source']}"))
    log(text(f"安装器家族: {record['installer_family']}", f"Installer family: {record['installer_family']}"))
    log(text(f"建议模式: {record['mode']}", f"Suggestion mode: {record['mode']}"))
    log(text(f"安装包: {record['installer_path']}", f"Installer: {record['installer_path']}"))
    log(text(f"建议安装目录: {record['target_dir']}", f"Suggested target: {record['target_dir']}"))
    log(text(f"命令预览（仅展示）: {record['preview']}", f"Command preview (display only): {record['preview']}"))
    log(text(f"当前状态: {record['status']}", f"Current status: {record['status']}"))
    log("=" * 60)


def run_install_record(
    record: dict[str, Any],
    *,
    apps_root: str | Path,
    installers_root: str | Path,
    target_dir: str | Path | None = None,
) -> bool:
    record_id = int(record["id"])
    claimed = claim_install_suggestion(record_id, expected_record=record)
    if claimed is None:
        log(text(f"安装建议 #{record_id} 无法领取。", f"Suggestion #{record_id} could not be claimed."))
        return False

    claim_id = claimed["claim_id"]
    try:
        installer = validate_installer_path(claimed["installer_path"], installers_root)
        final_target = validate_install_target(
            target_dir if target_dir is not None else claimed["target_dir"],
            apps_root,
        )
        final_fields = rebuild_execution_fields(
            {**claimed, "installer_path": str(installer)},
            final_target,
        )
    except (PathPolicyError, KeyError, TypeError, ValueError) as exc:
        finish_install_claim(record_id, claim_id, "blocked")
        log(text(f"安装建议因安全校验被阻止 #{record_id}: {exc}", f"Suggestion #{record_id} was blocked by safety validation: {exc}"))
        return False

    log(text(f"准备启动安装建议 #{record_id}: {final_fields['preview']}", f"Preparing to launch suggestion #{record_id}: {final_fields['preview']}"))
    launching = prepare_install_launch(record_id, claim_id, final_fields)
    if launching is None:
        return False

    # A crash from here until the result is saved leaves "launching" for manual review.
    argv = [launching["executable"], *launching["args"]]
    try:
        subprocess.Popen(argv, shell=False)
    except OSError as exc:
        status = "launch_failed"
        outcome = text(f"启动失败: {exc}", f"Process creation failed: {exc}")
    except Exception as exc:
        status = "launch_unknown"
        outcome = text(f"启动结果未知: {exc}", f"Launch outcome unknown: {exc}")
    else:
        status = "launched"
        outcome = text("已创建进程，安装结果尚未确认。", "Process created. Installation outcome is unconfirmed.")

    if finish_install_claim(record_id, claim_id, status) is None:
        raise JsonStoreError(f"Could not record {status} for suggestion #{record_id}. Check the queue.")
    log(f"#{record_id}: {outcome}")
    return status == "launched"
