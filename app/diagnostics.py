from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from rich import box
from rich.panel import Panel
from rich.table import Table

from app.core.console import console
from app.core.i18n import text, cell_text, title_text, status_text
from app.core.paths import (
    APP_HOME,
    CONFIG_DIR,
    DATA_DIR,
    LOG_DIR,
    ensure_user_config_files,
    get_installer_rules_path,
    get_pending_installs_path,
    get_rules_path,
    get_settings_path,
)
from app.core.settings import load_rules, load_settings
from app.installers.queue import load_pending_installs


def _path_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".pathpilot_write_test.tmp"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _add_result(
    table: Table,
    no: int,
    name_zh: str,
    name_en: str,
    passed: bool,
    detail_zh: str,
    detail_en: str,
    lang: str,
) -> None:
    table.add_row(
        str(no),
        cell_text(name_zh, name_en, lang),
        status_text("ok" if passed else "failed", lang),
        cell_text(detail_zh, detail_en, lang),
    )


def run_doctor_report(lang: str = "zh") -> bool:
    ensure_user_config_files()
    passed_all = True

    console.print(
        Panel(
            text(
                f"用户目录：{APP_HOME}\n配置目录：{CONFIG_DIR}\n数据目录：{DATA_DIR}",
                f"App home: {APP_HOME}\nConfig dir: {CONFIG_DIR}\nData dir: {DATA_DIR}",
                lang,
            ),
            title=title_text("PathPilot 诊断", "PathPilot Doctor", lang),
            border_style="cyan",
            box=box.SQUARE,
        )
    )

    table = Table(
        title=title_text("诊断结果", "Doctor Results", lang),
        box=box.SQUARE,
        show_lines=True,
        expand=False,
        border_style="cyan",
    )
    table.add_column("No.", style="magenta", width=4, justify="right")
    table.add_column(cell_text("检查项", "Check Item", lang), style="cyan", min_width=20)
    table.add_column(cell_text("状态", "Status", lang), style="green", min_width=10)
    table.add_column(cell_text("说明", "Detail", lang), min_width=42, overflow="fold")

    checks: list[tuple[str, str, bool, str, str]] = []

    settings_path = get_settings_path()
    rules_path = get_rules_path()
    installer_rules_path = get_installer_rules_path()
    pending_path = get_pending_installs_path()

    checks.append(("用户配置目录", "User config directory", CONFIG_DIR.exists(), f"配置目录：{CONFIG_DIR}", f"Config dir: {CONFIG_DIR}"))
    checks.append(("settings.json", "settings.json", settings_path.exists(), f"配置文件：{settings_path}", f"Settings file: {settings_path}"))
    checks.append(("rules.json", "rules.json", rules_path.exists(), f"分类规则：{rules_path}", f"Rules file: {rules_path}"))
    checks.append(("installer_rules.json", "installer_rules.json", installer_rules_path.exists(), f"安装器规则：{installer_rules_path}", f"Installer rules: {installer_rules_path}"))
    checks.append(("pending_installs.json", "pending_installs.json", pending_path.exists(), f"安装建议队列：{pending_path}", f"Install queue: {pending_path}"))

    try:
        settings = load_settings()
        runtime = settings["runtime_paths"]
        settings_ok = True
        settings_detail_zh = f"根目录：{runtime['root_dir']}"
        settings_detail_en = f"Root: {runtime['root_dir']}"
    except Exception as e:
        settings = {}
        runtime = {}
        settings_ok = False
        settings_detail_zh = f"读取失败：{e}"
        settings_detail_en = f"Failed to load: {e}"

    checks.append(("运行时配置", "Runtime settings", settings_ok, settings_detail_zh, settings_detail_en))

    root_dir = Path(runtime.get("root_dir", "")) if runtime else Path("")
    incoming_dir = Path(runtime.get("incoming_root", "")) if runtime else Path("")

    checks.append(("根目录可写", "Root writable", bool(runtime) and _path_writable(root_dir), f"根目录：{root_dir}", f"Root: {root_dir}"))
    checks.append(("Incoming 可写", "Incoming writable", bool(runtime) and _path_writable(incoming_dir), f"Incoming：{incoming_dir}", f"Incoming: {incoming_dir}"))

    try:
        rules = load_rules()
        rule_count = len(rules.get("rules", []))
        rules_ok = rule_count > 0
        rules_detail_zh = f"分类规则数量：{rule_count}"
        rules_detail_en = f"Rule count: {rule_count}"
    except Exception as e:
        rules_ok = False
        rules_detail_zh = f"读取失败：{e}"
        rules_detail_en = f"Failed to load: {e}"

    checks.append(("分类规则", "Classification rules", rules_ok, rules_detail_zh, rules_detail_en))

    try:
        queue = load_pending_installs()
        queue_ok = isinstance(queue, list)
        queue_detail_zh = f"安装建议数量：{len(queue)}"
        queue_detail_en = f"Suggestion count: {len(queue)}"
    except Exception as e:
        queue_ok = False
        queue_detail_zh = f"读取失败：{e}"
        queue_detail_en = f"Failed to load: {e}"

    checks.append(("安装建议队列", "Install queue", queue_ok, queue_detail_zh, queue_detail_en))

    pyside_ok = importlib.util.find_spec("PySide6") is not None
    checks.append((
        "GUI 依赖 PySide6",
        "GUI dependency PySide6",
        pyside_ok,
        "PySide6 可用" if pyside_ok else "未检测到 PySide6，GUI 可能无法启动",
        "PySide6 available" if pyside_ok else "PySide6 not found; GUI may not start",
    ))

    for index, (zh, en, passed, detail_zh, detail_en) in enumerate(checks, start=1):
        passed_all = passed_all and passed
        _add_result(table, index, zh, en, passed, detail_zh, detail_en, lang)

    console.print(table)

    console.print(
        Panel(
            text(
                f"Python：{sys.version.split()[0]}\n可执行文件：{sys.executable}\n工作目录：{Path.cwd()}",
                f"Python: {sys.version.split()[0]}\nExecutable: {sys.executable}\nWorking dir: {Path.cwd()}",
                lang,
            ),
            title=title_text("运行环境", "Runtime Environment", lang),
            border_style="green" if passed_all else "yellow",
            box=box.SQUARE,
        )
    )

    return passed_all


def run_self_test(lang: str = "zh") -> bool:
    passed = run_doctor_report(lang)

    if passed:
        console.print(
            Panel(
                text("PathPilot 基础自检通过。", "PathPilot basic self-test passed.", lang),
                title=title_text("完成", "Done", lang),
                border_style="green",
                box=box.SQUARE,
            )
        )
    else:
        console.print(
            Panel(
                text(
                    "PathPilot 自检未完全通过，请检查上方失败项。",
                    "PathPilot self-test did not fully pass. Please check failed items above.",
                    lang,
                ),
                title=title_text("需要处理", "Action Required", lang),
                border_style="red",
                box=box.SQUARE,
            )
        )

    return passed
