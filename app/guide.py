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
        ("3", "pathpilot commands", cell_text("快捷查看全部常用命令", "Show common commands", lang)),
        ("4", "pathpilot doctor", cell_text("检查配置、目录、规则和依赖", "Check config, directories, rules and dependencies", lang)),
        ("5", "pathpilot test", cell_text("运行 PathPilot 基础自检", "Run PathPilot basic self-test", lang)),
        ("6", "pathpilot status", cell_text("查看运行状态、根目录和监听目录", "Show runtime status, roots and sources", lang)),
        ("7", "pathpilot watch", cell_text("启动下载目录监听", "Start watching source directories", lang)),
        ("8", "pathpilot ui", cell_text("打开图形界面", "Open GUI window", lang)),
        ("9", "pathpilot installs list", cell_text("查看待处理安装建议", "List pending install suggestions", lang)),
        ("10", "pathpilot installs list --all", cell_text("查看全部安装建议历史", "List all install suggestions", lang)),
        ("11", "pathpilot installs detail <id>", cell_text("查看某条安装建议详情", "Show install suggestion detail", lang)),
        ("12", "pathpilot installs run <id>", cell_text("执行 auto/try 安装建议", "Run an auto/try install suggestion", lang)),
        ("13", "pathpilot installs run <id> --force", cell_text("强制执行 suggest 建议", "Force-run a suggest suggestion", lang)),
        ("14", "pathpilot installs skip <id>", cell_text("跳过安装建议", "Skip install suggestion", lang)),
        ("15", "pathpilot sources list", cell_text("查看监听来源目录", "List source directories", lang)),
        ("16", "pathpilot sources add <path>", cell_text("添加软件/浏览器下载目录", "Add software/browser download folder", lang)),
        ("17", "pathpilot config show", cell_text("显示配置文件", "Show config file", lang)),
        ("18", "pathpilot config set-root <path>", cell_text("设置 PathPilot 根目录", "Set PathPilot root directory", lang)),
        ("19", "pathpilot --lang en guide", cell_text("临时切换英文输出", "Temporarily switch to English", lang)),
        ("20", "pathpilot --lang bi guide", cell_text("临时切换双语输出", "Temporarily switch to bilingual output", lang)),
        ("21", "pathpilot -v", cell_text("查看版本号", "Show version", lang)),
    ]

    for row in rows:
        table.add_row(*row)

    console.print(table)

    console.print(
        Panel(
            text(
                "建议测试顺序：`pathpilot doctor` → `pathpilot status` → `pathpilot watch` → 拖入测试文件。",
                "Suggested test order: `pathpilot doctor` → `pathpilot status` → `pathpilot watch` → drop test files.",
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
