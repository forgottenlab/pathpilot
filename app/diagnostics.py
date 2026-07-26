from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

from rich import box
from rich.panel import Panel
from rich.table import Table

from app.core.console import console
from app.core.i18n import cell_text, status_text, text, title_text
from app.core.json_store import (
    JsonStoreError,
    atomic_write_json,
    inspect_json,
    read_json_snapshot,
)
from app.core.paths import (
    ensure_user_config_files,
    get_app_home,
    get_config_dir,
    get_data_dir,
    get_installer_rules_path,
    get_pending_installs_path,
    get_rules_path,
    get_settings_path,
)
from app.core.settings import load_rules, load_settings
from app.files.watcher import DownloadEventHandler


def _path_writable_readonly(path: Path) -> bool:
    return path.exists() and path.is_dir() and os.access(path, os.W_OK)


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
    """Inspect current state without creating, rewriting, or locking any file."""
    app_home = get_app_home()
    config_dir = get_config_dir()
    data_dir = get_data_dir()
    passed_all = True

    console.print(
        Panel(
            text(
                f"用户目录：{app_home}\n配置目录：{config_dir}\n数据目录：{data_dir}",
                f"App home: {app_home}\nConfig dir: {config_dir}\nData dir: {data_dir}",
                lang,
            ),
            title=title_text("PathPilot 诊断（只读）", "PathPilot Doctor (read-only)", lang),
            border_style="cyan",
            box=box.SQUARE,
        )
    )

    table = Table(
        title=title_text("诊断结果", "Doctor Results", lang),
        box=box.SQUARE,
        show_lines=True,
        border_style="cyan",
    )
    table.add_column("No.", style="magenta", width=4, justify="right")
    table.add_column(cell_text("检查项", "Check Item", lang), style="cyan", min_width=20)
    table.add_column(cell_text("状态", "Status", lang), style="green", min_width=10)
    table.add_column(cell_text("说明", "Detail", lang), min_width=42, overflow="fold")

    checks: list[tuple[str, str, bool, str, str]] = []
    checks.append((
        "用户配置目录",
        "User config directory",
        config_dir.exists(),
        f"配置目录：{config_dir}",
        f"Config dir: {config_dir}",
    ))

    json_specs = (
        ("settings.json", get_settings_path(), dict),
        ("rules.json", get_rules_path(), dict),
        ("installer_rules.json", get_installer_rules_path(), dict),
        ("pending_installs.json", get_pending_installs_path(), list),
    )
    for name, path, expected in json_specs:
        state = inspect_json(path, expected_type=expected)
        detail = str(path) if state.valid else f"{path}: {state.error}"
        checks.append((name, name, state.valid, detail, detail))

    try:
        settings = load_settings(
            create_missing=False,
            create_runtime_dirs=False,
            readonly=True,
        )
        runtime = settings["runtime_paths"]
        settings_ok = True
        settings_detail = f"Root: {runtime['root_dir']}"
    except Exception as exc:
        runtime = {}
        settings_ok = False
        settings_detail = f"Failed to load: {exc}"
    checks.append(("运行时配置", "Runtime settings", settings_ok, settings_detail, settings_detail))

    root_dir = Path(runtime["root_dir"]) if runtime else Path()
    incoming_dir = Path(runtime["incoming_root"]) if runtime else Path()
    checks.append((
        "根目录可写",
        "Root writable",
        bool(runtime) and _path_writable_readonly(root_dir),
        f"根目录：{root_dir}",
        f"Root: {root_dir}",
    ))
    checks.append((
        "Incoming 可写",
        "Incoming writable",
        bool(runtime) and _path_writable_readonly(incoming_dir),
        f"Incoming：{incoming_dir}",
        f"Incoming: {incoming_dir}",
    ))

    try:
        rules = load_rules(create_missing=False, readonly=True)
        count = len(rules.get("rules", []))
        checks.append(("分类规则", "Classification rules", count > 0, f"规则数量：{count}", f"Rule count: {count}"))
    except Exception as exc:
        checks.append(("分类规则", "Classification rules", False, f"读取失败：{exc}", f"Failed to load: {exc}"))

    try:
        queue = read_json_snapshot(get_pending_installs_path(), expected_type=list)
        checks.append(("安装建议队列", "Install queue", True, f"建议数量：{len(queue)}", f"Suggestion count: {len(queue)}"))
    except Exception as exc:
        checks.append(("安装建议队列", "Install queue", False, f"读取失败：{exc}", f"Failed to load: {exc}"))

    pyside_ok = importlib.util.find_spec("PySide6") is not None
    checks.append((
        "GUI 依赖 PySide6",
        "GUI dependency PySide6",
        pyside_ok,
        "PySide6 可用" if pyside_ok else "未检测到 PySide6",
        "PySide6 available" if pyside_ok else "PySide6 not found",
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
    """Run an isolated behavior check without consulting the active user state."""
    original_home = os.environ.get("PATHPILOT_HOME")
    try:
        with tempfile.TemporaryDirectory(prefix="pathpilot-self-test-") as temp_name:
            temp_root = Path(temp_name).resolve()
            os.environ["PATHPILOT_HOME"] = str(temp_root / "home")
            managed_root = temp_root / "managed"
            source = temp_root / "source"
            source.mkdir(parents=True)
            ensure_user_config_files()

            settings_path = get_settings_path()
            settings_data = {
                "watch_directories": [str(source)],
                "base_paths": {"root_dir": str(managed_root)},
                "behavior": {
                    "ignore_hidden_files": True,
                    "stable_check_seconds": 0,
                    "stable_checks": 1,
                    "create_missing_dirs": True,
                    "overwrite_strategy": "rename",
                },
            }
            atomic_write_json(settings_path, settings_data)
            settings = load_settings()
            rules = load_rules()

            fixture = source / "pathpilot-self-test.txt"
            fixture.write_text("isolated", encoding="utf-8")
            handler = DownloadEventHandler(settings, rules)
            handler._handle_file(fixture)
            incoming = Path(settings["runtime_paths"]["incoming_root"]) / fixture.name
            handler._handle_file(incoming)
            final_path = (
                Path(settings["runtime_paths"]["archive_root"])
                / "05-Documents"
                / "Mixed"
                / fixture.name
            )
            passed = final_path.exists() and not fixture.exists()
    except (JsonStoreError, OSError, KeyError, ValueError) as exc:
        console.print(f"[red]{text('隔离自检失败', 'Isolated self-test failed', lang)}: {exc}[/red]")
        passed = False
    finally:
        if original_home is None:
            os.environ.pop("PATHPILOT_HOME", None)
        else:
            os.environ["PATHPILOT_HOME"] = original_home

    console.print(
        Panel(
            text(
                "PathPilot 隔离行为自检通过。" if passed else "PathPilot 隔离行为自检失败。",
                "PathPilot isolated behavior self-test passed." if passed else "PathPilot isolated behavior self-test failed.",
                lang,
            ),
            title=title_text("完成" if passed else "需要处理", "Done" if passed else "Action Required", lang),
            border_style="green" if passed else "red",
            box=box.SQUARE,
        )
    )
    return passed
