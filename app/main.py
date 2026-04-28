from __future__ import annotations

from app.installers.queue import get_pending_items
from app.core.logger import log
from app.core.settings import load_rules, load_settings
from app.files.watcher import start_watching


def format_gb(num_bytes: int) -> str:
    return f"{num_bytes / (1024 ** 3):.2f} GB"


def main() -> None:
    log("PathPilot 启动中...")
    settings = load_settings()
    rules = load_rules()

    runtime_paths = settings["runtime_paths"]
    log(f"系统盘: {runtime_paths['system_drive']}")
    log(f"根目录选择原因: {runtime_paths['root_selection_reason']}")
    log(f"当前 PathPilot 根目录: {runtime_paths['root_dir']}")
    log(f"归档根目录 archive_root: {runtime_paths['archive_root']}")
    log(f"应用根目录 apps_root: {runtime_paths['apps_root']}")
    log(f"Incoming 目录: {runtime_paths['incoming_root']}")

    disk_candidates = runtime_paths.get("_disk_candidates", [])
    if disk_candidates:
        for item in disk_candidates:
            log(f"候选盘: {item['drive']} | 剩余空间: {format_gb(item['free_bytes'])}")

    pending_count = len(get_pending_items())
    log(f"当前待处理安装建议数量: {pending_count}")

    start_watching(settings, rules)


if __name__ == "__main__":
    main()

