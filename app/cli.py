from __future__ import annotations

import json
import os
from pathlib import Path

import typer
from rich import box
from rich.table import Table

from app import __version__
from app.core.console import (
    console,
    banner,
    ok,
    info,
    warn,
    error,
    kv_table,
    path_list,
    print_json_text,
)
from app.core.i18n import (
    set_lang,
    normalize_lang,
    text,
    cell_text,
    title_text,
)
from app.core.paths import CONFIG_DIR, ensure_user_config_files
from app.core.settings import load_rules, load_settings
from app.diagnostics import run_doctor_report, run_self_test
from app.files.watcher import start_watching
from app.guide import show_command_guide
from app.installers.queue import (
    get_pending_items,
    load_pending_installs,
    update_install_suggestion_status,
)
from app.installers.runner import run_install_record


SETTINGS_FILE = CONFIG_DIR / "settings.json"

app = typer.Typer(
    name="pathpilot",
    help="PathPilot - Downloads and installation path governance assistant.",
    no_args_is_help=False,
)

config_app = typer.Typer(help="配置管理 / Config management")
sources_app = typer.Typer(help="监听来源目录管理 / Source directory management")
installs_app = typer.Typer(help="安装建议管理 / Install suggestion management")

app.add_typer(config_app, name="config")
app.add_typer(sources_app, name="sources")
app.add_typer(installs_app, name="installs")

GLOBAL_LANG_OVERRIDE: str | None = None


def normalize_display_name(name: str) -> str:
    if name.endswith(")"):
        left = name.rfind(" (")
        if left != -1:
            tail = name[left + 2:-1]
            if tail.isdigit():
                return name[:left]
    return name


def apply_language(command_lang: str | None = None) -> str:
    if command_lang:
        final_lang = normalize_lang(command_lang)
    elif GLOBAL_LANG_OVERRIDE:
        final_lang = normalize_lang(GLOBAL_LANG_OVERRIDE)
    else:
        final_lang = "zh"

    set_lang(final_lang)
    return final_lang


def load_settings_file() -> dict:
    ensure_user_config_files()
    if not SETTINGS_FILE.exists():
        return {}
    with SETTINGS_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def save_settings_file(settings: dict) -> None:
    ensure_user_config_files()
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SETTINGS_FILE.open("w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def format_gb(num_bytes: int) -> str:
    return f"{num_bytes / (1024 ** 3):.2f} GB"


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    lang: str | None = typer.Option(None, "--lang", "-l", help="Language: zh / en / bi"),
    version_flag: bool = typer.Option(False, "--version", "-v", help="Show PathPilot version and exit."),
) -> None:
    global GLOBAL_LANG_OVERRIDE

    if lang:
        GLOBAL_LANG_OVERRIDE = normalize_lang(lang)
        set_lang(GLOBAL_LANG_OVERRIDE)

    if version_flag:
        console.print(f"PathPilot {__version__}")
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        active_lang = apply_language(lang)
        console.print(f"[bold]{text('PathPilot 命令行工具', 'PathPilot command line tool', active_lang)}[/bold]")
        show_command_guide(active_lang)


@app.command()
def guide(
    lang: str | None = typer.Option(None, "--lang", "-l", help="Language: zh / en / bi"),
) -> None:
    active_lang = apply_language(lang)
    show_command_guide(active_lang)


@app.command()
def commands(
    lang: str | None = typer.Option(None, "--lang", "-l", help="Language: zh / en / bi"),
) -> None:
    active_lang = apply_language(lang)
    show_command_guide(active_lang)


@app.command()
def doctor(
    lang: str | None = typer.Option(None, "--lang", "-l", help="Language: zh / en / bi"),
) -> None:
    active_lang = apply_language(lang)
    passed = run_doctor_report(active_lang)
    if not passed:
        raise typer.Exit(code=1)


@app.command()
def test(
    lang: str | None = typer.Option(None, "--lang", "-l", help="Language: zh / en / bi"),
) -> None:
    active_lang = apply_language(lang)
    passed = run_self_test(active_lang)
    if not passed:
        raise typer.Exit(code=1)


@app.command()
def version(
    lang: str | None = typer.Option(None, "--lang", "-l", help="Language: zh / en / bi"),
) -> None:
    apply_language(lang)
    console.print(f"PathPilot {__version__}")


@app.command()
def status(
    lang: str | None = typer.Option(None, "--lang", "-l", help="Language: zh / en / bi"),
) -> None:
    active_lang = apply_language(lang)
    settings = load_settings()
    runtime = settings["runtime_paths"]
    pending_count = len(get_pending_items())

    banner(
        "PathPilot",
        text("下载与安装路径治理助手", "Downloads and installation path governance assistant", active_lang),
    )

    kv_table(
        title_text("运行状态", "Runtime Status", active_lang),
        [
            (cell_text("系统盘", "System Drive", active_lang), runtime["system_drive"]),
            (cell_text("根目录", "Root", active_lang), runtime["root_dir"]),
            ("Downloads", runtime["archive_root"]),
            ("Apps", runtime["apps_root"]),
            ("Incoming", runtime["incoming_root"]),
            (cell_text("根目录选择原因", "Root Selection Reason", active_lang), runtime["root_selection_reason"]),
            (cell_text("待处理安装建议", "Pending Suggestions", active_lang), pending_count),
        ],
    )

    candidates = runtime.get("_disk_candidates", [])
    if candidates:
        table = Table(
            title=title_text("候选磁盘", "Candidate Disks", active_lang),
            box=box.SQUARE,
            show_lines=True,
            expand=False,
            border_style="cyan",
        )
        table.add_column(cell_text("盘符", "Drive", active_lang), style="cyan", width=8)
        table.add_column(cell_text("剩余空间", "Free Space", active_lang), justify="right", min_width=14)
        for item in candidates:
            table.add_row(item["drive"], format_gb(item["free_bytes"]))
        console.print(table)

    path_list(title_text("监听目录", "Source Directories", active_lang), settings.get("watch_directories", []))


@app.command()
def watch(
    lang: str | None = typer.Option(None, "--lang", "-l", help="Language: zh / en / bi"),
) -> None:
    active_lang = apply_language(lang)
    settings = load_settings()
    rules = load_rules()

    banner("PathPilot Watcher", text("开始监听下载入口目录", "Start watching source directories", active_lang))
    path_list(title_text("监听目录", "Source Directories", active_lang), settings.get("watch_directories", []))
    info(text("按 Ctrl + C 可停止监听。", "Press Ctrl + C to stop watching.", active_lang))

    start_watching(settings, rules)


@app.command()
def ui() -> None:
    from app.gui.start_gui import main as start_gui
    start_gui()


@config_app.command("show")
def config_show() -> None:
    ensure_user_config_files()
    banner("PathPilot Config", "settings.json")
    settings = load_settings_file()
    print_json_text(json.dumps(settings, ensure_ascii=False, indent=2))


@config_app.command("set-root")
def config_set_root(path: str) -> None:
    settings = load_settings_file()
    settings.setdefault("base_paths", {})
    settings["base_paths"]["root_dir"] = path.replace("\\", "/")
    save_settings_file(settings)

    ok(f"已设置 PathPilot 根目录: {settings['base_paths']['root_dir']}")
    warn("重启 PathPilot watcher 或重新打开 GUI 后生效。")


@config_app.command("reset-root")
def config_reset_root() -> None:
    settings = load_settings_file()
    settings.setdefault("base_paths", {})
    settings["base_paths"]["root_dir"] = ""
    save_settings_file(settings)

    ok("已重置为自动选择根目录。")
    warn("重启 PathPilot watcher 或重新打开 GUI 后生效。")


@sources_app.command("list")
def sources_list() -> None:
    settings = load_settings_file()
    watch_dirs = settings.get("watch_directories", [])

    banner("PathPilot Sources", "监听来源目录")
    if not watch_dirs:
        warn("当前没有配置监听目录。")
        return

    path_list("当前监听目录", watch_dirs)


@sources_app.command("add")
def sources_add(path: str) -> None:
    settings = load_settings_file()
    watch_dirs = settings.setdefault("watch_directories", [])

    final_path = path.replace("\\", "/")
    if final_path in watch_dirs:
        warn(f"监听目录已存在: {final_path}")
        return

    watch_dirs.append(final_path)
    save_settings_file(settings)

    ok(f"已添加监听目录: {final_path}")
    warn("重启 PathPilot watcher 后生效。")


@sources_app.command("remove")
def sources_remove(path: str) -> None:
    settings = load_settings_file()
    watch_dirs = settings.setdefault("watch_directories", [])

    target = path.replace("\\", "/")
    if target not in watch_dirs:
        warn(f"未找到监听目录: {target}")
        return

    watch_dirs.remove(target)
    save_settings_file(settings)

    ok(f"已移除监听目录: {target}")
    warn("重启 PathPilot watcher 后生效。")


def render_installs_table(items: list[dict]) -> None:
    table = Table(
        title="安装建议",
        box=box.SQUARE,
        show_lines=True,
        expand=False,
        border_style="cyan",
    )
    table.add_column("ID", justify="right", style="magenta", width=4)
    table.add_column("名称", style="cyan", min_width=14, overflow="fold")
    table.add_column("来源", min_width=10)
    table.add_column("家族", min_width=12)
    table.add_column("模式", min_width=8)
    table.add_column("状态", min_width=8)
    table.add_column("目标目录", min_width=42, overflow="fold")

    for item in items:
        mode = item.get("mode", "")
        status = item.get("status", "")

        mode_text = mode
        if mode == "auto":
            mode_text = f"[green]{mode}[/green]"
        elif mode == "try":
            mode_text = f"[yellow]{mode}[/yellow]"
        elif mode == "suggest":
            mode_text = f"[blue]{mode}[/blue]"

        status_style = {
            "pending": "yellow",
            "executed": "green",
            "skipped": "dim",
        }.get(status, "white")

        table.add_row(
            str(item.get("id", "")),
            normalize_display_name(str(item.get("name", ""))),
            str(item.get("source", "")),
            str(item.get("family", "")),
            mode_text,
            f"[{status_style}]{status}[/{status_style}]",
            str(item.get("target", "")),
        )

    console.print(table)


@installs_app.command("list")
def installs_list(
    all_items: bool = typer.Option(False, "--all", help="Show all suggestions, not only pending."),
) -> None:
    items_all = load_pending_installs()
    items = items_all if all_items else [item for item in items_all if item.get("status") == "pending"]

    banner("PathPilot Installs", "安装建议管理")

    if not items:
        warn("当前没有符合条件的安装建议。")
        return

    render_installs_table(items)


@installs_app.command("detail")
def installs_detail(id: int) -> None:
    items = load_pending_installs()
    record = next((x for x in items if int(x["id"]) == int(id)), None)

    if not record:
        error(f"未找到安装建议 #{id}")
        raise typer.Exit(code=1)

    banner(f"Install Suggestion #{record['id']}", normalize_display_name(record["name"]))

    kv_table(
        "详情",
        [
            ("名称", normalize_display_name(record.get("name", ""))),
            ("来源", record.get("source", "")),
            ("家族", record.get("family", "")),
            ("模式", record.get("mode", "")),
            ("状态", record.get("status", "")),
            ("安装包", record.get("installer", "")),
            ("目标目录", record.get("target", "")),
            ("命令", record.get("command", "")),
            ("创建时间", record.get("created_at", "")),
            ("更新时间", record.get("updated_at", "")),
        ],
    )


@installs_app.command("run")
def installs_run(
    id: int,
    target: str | None = typer.Option(None, "--target", help="Use a custom installation target."),
    force: bool = typer.Option(False, "--force", help="Force-run suggest-mode suggestion."),
) -> None:
    items = load_pending_installs()
    record = next((x for x in items if int(x["id"]) == int(id)), None)

    if not record:
        error(f"未找到安装建议 #{id}")
        raise typer.Exit(code=1)

    if record.get("status") != "pending":
        warn(f"安装建议 #{id} 当前状态不是 pending，而是 {record.get('status')}")
        raise typer.Exit(code=0)

    if record.get("mode") == "suggest" and not force:
        warn("当前建议为 suggest 模式，默认不执行。")
        info("确认要执行可添加 --force。")
        raise typer.Exit(code=0)

    if target:
        new_target = target.replace("\\", "/")
        old_target = record["target"]
        record["target"] = new_target
        record["command"] = record["command"].replace(old_target, new_target)

    ok(f"准备执行安装建议 #{record['id']}: {normalize_display_name(record['name'])}")
    info(f"命令: {record['command']}")

    result = run_install_record(record)
    if result:
        ok(f"安装建议 #{id} 已启动执行。")
    else:
        error(f"安装建议 #{id} 执行失败。")
        raise typer.Exit(code=1)


@installs_app.command("skip")
def installs_skip(id: int) -> None:
    updated = update_install_suggestion_status(int(id), "skipped")
    if not updated:
        error(f"未找到安装建议 #{id}")
        raise typer.Exit(code=1)

    ok(f"安装建议 #{id} 已标记为 skipped。")


@installs_app.command("open")
def installs_open(id: int) -> None:
    items = load_pending_installs()
    record = next((x for x in items if int(x["id"]) == int(id)), None)

    if not record:
        error(f"未找到安装建议 #{id}")
        raise typer.Exit(code=1)

    installer_path = Path(record["installer"])
    if installer_path.exists():
        os.startfile(str(installer_path.parent))
        ok(f"已打开安装包所在目录: {installer_path.parent}")
    else:
        error(f"安装包不存在: {installer_path}")
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

