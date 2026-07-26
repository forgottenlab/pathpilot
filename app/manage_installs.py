from __future__ import annotations

import sys

from app.installers.queue import (
    get_pending_items,
    load_pending_installs,
    update_install_suggestion_status,
)
from app.core.logger import log


def list_pending() -> None:
    items = get_pending_items()
    if not items:
        log("当前没有待处理安装建议。")
        return

    log("待处理安装建议列表：")
    for item in items:
        log(
            f"#{item['id']} | {item['name']} | "
            f"family={item.get('installer_family', item.get('family', ''))} | "
            f"mode={item['mode']} | "
            f"target={item.get('target_dir', item.get('target', ''))}"
        )


def run_one(record_id: int) -> None:
    items = load_pending_installs()
    record = next((x for x in items if int(x["id"]) == record_id), None)
    if not record:
        log(f"未找到安装建议 #{record_id}")
        return

    if record.get("status") != "pending":
        log(f"安装建议 #{record_id} 当前状态不是 pending，而是 {record.get('status')}")
        return

    log(
        "旧式 app.manage_installs 入口不再允许启动安装器；"
        f"请使用 pathpilot installs run {record_id} --force 进行显式确认。"
    )


def skip_one(record_id: int) -> None:
    updated = update_install_suggestion_status(record_id, "skipped")
    if not updated:
        log(f"未找到安装建议 #{record_id}")
        return
    log(f"安装建议 #{record_id} 已标记为 skipped。")


def main() -> None:
    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m app.manage_installs list")
        print("  python -m app.manage_installs run <id>")
        print("  python -m app.manage_installs skip <id>")
        return

    cmd = sys.argv[1].lower()

    if cmd == "list":
        list_pending()
        return

    if cmd in {"run", "skip"}:
        if len(sys.argv) < 3:
            print(f"缺少 id: python -m app.manage_installs {cmd} <id>")
            return

        try:
            record_id = int(sys.argv[2])
        except ValueError:
            print("id 必须是整数")
            return

        if cmd == "run":
            run_one(record_id)
        else:
            skip_one(record_id)
        return

    print(f"未知命令: {cmd}")


if __name__ == "__main__":
    main()

