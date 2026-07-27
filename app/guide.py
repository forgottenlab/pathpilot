from __future__ import annotations

from rich.panel import Panel
from rich.table import Table
from rich import box

from app.core.console import console
from app.core.i18n import text, cell_text, title_text


def show_command_guide(lang: str = "zh") -> None:
    table = Table(
        title=title_text("PathPilot 基础指引", "PathPilot Quick Guide", lang),
        box=box.SQUARE,
        show_lines=True,
        expand=False,
        border_style="cyan",
    )

    table.add_column("No.", style="magenta", width=4, justify="right")
    table.add_column(cell_text("命令", "Command", lang), style="cyan", min_width=32)
    table.add_column(cell_text("用途", "Description", lang), min_width=52)

    rows = [
        ("1", "pathpilot", cell_text("显示此基础指引", "Show this quick guide", lang)),
        ("2", "pathpilot guide", cell_text("显示基础使用指引", "Show quick guide", lang)),
        ("3", "pathpilot commands", cell_text("查看完整命令指引", "Show the complete command guide", lang)),
        ("4", "pathpilot doctor", cell_text("只读检查配置、目录、规则和依赖", "Read-only checks for state, paths, rules, and dependencies", lang)),
        ("5", "pathpilot test", cell_text("在临时环境运行隔离行为测试", "Run isolated behavior checks in temporary state", lang)),
        ("6", "pathpilot status", cell_text("查看运行状态、根目录和监听目录", "Show runtime status, roots and sources", lang)),
        ("7", "pathpilot watch", cell_text("持续监听配置的来源目录", "Continuously watch configured source directories", lang)),
        ("8", "pathpilot ui", cell_text("打开可选 GUI 界面", "Open the optional GUI", lang)),
        ("9", "pathpilot installs list", cell_text("查看待处理安装建议", "List pending install suggestions", lang)),
        ("10", "pathpilot installs list --all", cell_text("查看全部安装建议历史", "List all install suggestions", lang)),
        ("11", "pathpilot installs detail <id>", cell_text("查看某条安装建议详情", "Show install suggestion detail", lang)),
        ("12", "pathpilot installs run <id> --force", cell_text("显式确认启动；不能绕过安全检查", "Confirm launch explicitly; safety checks remain enforced", lang)),
        ("13", "pathpilot installs skip <id>", cell_text("跳过安装建议", "Skip install suggestion", lang)),
        ("14", "pathpilot installs open <id>", cell_text("打开安装包所在目录", "Open the installer directory", lang)),
        ("15", "pathpilot sources list", cell_text("查看监听来源目录", "List source directories", lang)),
        ("16", "pathpilot sources add <path>", cell_text("添加外部下载目录", "Add an external download directory", lang)),
        ("17", "pathpilot sources remove <path>", cell_text("移除监听来源目录", "Remove a source directory", lang)),
        ("18", "pathpilot config show", cell_text("显示配置文件", "Show the configuration file", lang)),
        ("19", "pathpilot config set-root <path>", cell_text("设置 PathPilot 根目录", "Set the PathPilot root", lang)),
        ("20", "pathpilot config reset-root", cell_text("恢复自动根目录选择", "Restore automatic root selection", lang)),
        ("21", "pathpilot version / -v / --version", cell_text("查看版本号", "Show the version", lang)),
        ("22", "pathpilot --lang en guide", cell_text("临时切换英文输出", "Use English output", lang)),
        ("23", "pathpilot --lang bi guide", cell_text("临时切换双语输出", "Use bilingual output", lang)),
    ]

    for row in rows:
        table.add_row(*row)

    console.print(table)

    console.print(
        Panel(
            text(
                "建议测试顺序：`pathpilot status` → `pathpilot doctor` → `pathpilot test` → `pathpilot watch`。",
                "Suggested test order: `pathpilot status` → `pathpilot doctor` → `pathpilot test` → `pathpilot watch`.",
                lang,
            ),
            title=title_text("测试建议", "Test Tip", lang),
            border_style="cyan",
            box=box.SQUARE,
        )
    )

    console.print(
        Panel(
            text(
                "首次安装：运行 `scripts/install.ps1` 或 README 中的一键安装命令。\n"
                "更新：运行 `scripts/update.ps1`，或重新运行安装脚本。\n"
                "卸载：运行 `scripts/uninstall.ps1`，或执行 `python -m pipx uninstall pathpilot`。",
                "First install: run `scripts/install.ps1` or the one-line command in README.\n"
                "Update: run `scripts/update.ps1`, or rerun the installer.\n"
                "Uninstall: run `scripts/uninstall.ps1`, or run `python -m pipx uninstall pathpilot`.",
                lang,
            ),
            title=title_text("安装 / 更新 / 卸载", "Install / Update / Uninstall", lang),
            border_style="green",
            box=box.SQUARE,
        )
    )
