from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.logger import log
from app.core.i18n import text
from app.core.path_policy import PathPolicyError, validate_installer_path, validate_install_target
from app.installers.queue import update_install_suggestion_record
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


def _is_legacy_record(record: dict[str, Any]) -> bool:
    return record.get("status") == "legacy_unsafe" or (
        "command" in record
        and not all(
            key in record
            for key in (
                "executable",
                "args",
                "installer_path",
                "target_dir",
                "installer_family",
            )
        )
    )


def run_install_record(
    record: dict[str, Any],
    *,
    apps_root: str | Path,
    installers_root: str | Path,
    target_dir: str | Path | None = None,
) -> bool:
    record_id = int(record["id"])

    if _is_legacy_record(record):
        update_install_suggestion_record(record_id, {"status": "legacy_unsafe"})
        log(text(f"安装建议 #{record_id} 是旧版 command-only 记录，已拒绝执行。", f"Suggestion #{record_id} is a legacy command-only record and was rejected."))
        return False

    try:
        if record.get("status") != "pending":
            raise ValueError(f"Record status is not pending: {record.get('status')}")

        installer = validate_installer_path(record["installer_path"], installers_root)
        final_target = validate_install_target(
            target_dir if target_dir is not None else record["target_dir"],
            apps_root,
        )
        final_fields = rebuild_execution_fields(
            {**record, "installer_path": str(installer)},
            final_target,
        )
        confirmed_at = datetime.now().isoformat(timespec="seconds")
        persisted = update_install_suggestion_record(
            record_id,
            {
                **final_fields,
                "confirmed_at": confirmed_at,
                "status": "pending",
            },
        )
        if persisted is None:
            raise ValueError(f"Install suggestion no longer exists: {record_id}")

        argv = [final_fields["executable"], *final_fields["args"]]
        log(text(f"开始启动安装建议 #{record_id}: {final_fields['preview']}", f"Launching suggestion #{record_id}: {final_fields['preview']}"))
        subprocess.Popen(argv, shell=False)
    except (PathPolicyError, KeyError, TypeError, ValueError) as exc:
        update_install_suggestion_record(record_id, {"status": "blocked"})
        log(text(f"安装建议因安全校验被阻止 #{record_id}: {exc}", f"Suggestion #{record_id} was blocked by safety validation: {exc}"))
        return False
    except Exception as exc:
        update_install_suggestion_record(record_id, {"status": "launch_failed"})
        log(text(f"安装建议启动失败 #{record_id}: {exc}", f"Suggestion #{record_id} failed to launch: {exc}"))
        return False

    update_install_suggestion_record(record_id, {"status": "launched"})
    log(text(f"安装建议 #{record_id} 已启动进程；这不代表安装成功。", f"Suggestion #{record_id} process launched; this does not mean installation succeeded."))
    return True
