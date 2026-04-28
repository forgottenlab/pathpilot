from __future__ import annotations

import subprocess

from app.installers.queue import update_install_suggestion_status
from app.core.logger import log


def log_install_suggestion(record: dict) -> None:
    log("=" * 60)
    log(f"已生成安装建议 #{record['id']}")
    log(f"名称: {record['name']}")
    log(f"来源类型: {record['source']}")
    log(f"安装器家族: {record['family']}")
    log(f"建议模式: {record['mode']}")
    log(f"安装包: {record['installer']}")
    log(f"建议安装目录: {record['target']}")
    log(f"建议命令: {record['command']}")
    log(f"当前状态: {record['status']}")
    log("=" * 60)


def run_install_record(record: dict) -> bool:
    try:
        record_id = int(record["id"])
        command = record["command"]

        log(f"开始执行安装建议 #{record_id}: {command}")
        subprocess.Popen(command, shell=True)
        update_install_suggestion_status(record_id, "executed")
        log(f"安装建议 #{record_id} 已启动执行。")
        return True
    except Exception as e:
        log(f"安装建议执行失败: {e}")
        return False
