from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.logger import log
from app.core.path_policy import PathPolicyError, validate_installer_path, validate_install_target
from app.installers.queue import update_install_suggestion_record
from app.installers.strategy import rebuild_execution_fields


def log_install_suggestion(record: dict[str, Any]) -> None:
    log("=" * 60)
    log(f"已生成安装建议 #{record['id']}")
    log(f"名称: {record['name']}")
    log(f"来源类型: {record['source']}")
    log(f"安装器家族: {record['installer_family']}")
    log(f"建议模式: {record['mode']}")
    log(f"安装包: {record['installer_path']}")
    log(f"建议安装目录: {record['target_dir']}")
    log(f"命令预览（仅展示）: {record['preview']}")
    log(f"当前状态: {record['status']}")
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
        log(f"安装建议 #{record_id} 是旧版 command-only 记录，已拒绝执行。")
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
        log(f"开始启动安装建议 #{record_id}: {final_fields['preview']}")
        subprocess.Popen(argv, shell=False)
    except (PathPolicyError, KeyError, TypeError, ValueError) as exc:
        update_install_suggestion_record(record_id, {"status": "blocked"})
        log(f"安装建议因安全校验被阻止 #{record_id}: {exc}")
        return False
    except Exception as exc:
        update_install_suggestion_record(record_id, {"status": "launch_failed"})
        log(f"安装建议启动失败 #{record_id}: {exc}")
        return False

    update_install_suggestion_record(record_id, {"status": "launched"})
    log(f"安装建议 #{record_id} 已启动进程；这不代表安装成功。")
    return True
