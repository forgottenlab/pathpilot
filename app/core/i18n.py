from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_LANGS = {"zh", "en", "bi"}

MESSAGES: dict[str, tuple[str, str]] = {
    "restart_required": (
        "重启 PathPilot watcher 或重新打开 GUI 后生效。",
        "Restart the PathPilot watcher or reopen the GUI to apply the change.",
    ),
    "watcher_restart_required": (
        "重启 PathPilot watcher 后生效。",
        "Restart the PathPilot watcher to apply the change.",
    ),
    "no_sources": ("当前没有配置监听目录。", "No source directories are configured."),
    "no_suggestions": (
        "当前没有符合条件的安装建议。",
        "No install suggestions match the current filter.",
    ),
    "suggest_confirmation": (
        "当前建议为 suggest 模式，默认不启动。",
        "This suggestion is in suggest mode and is not launched by default.",
    ),
    "force_safety": (
        "添加 --force 可显式确认启动；核心安全校验仍不可绕过。",
        "Add --force to confirm launch; core safety checks still cannot be bypassed.",
    ),
    "gui_extra_missing": (
        "未安装 GUI 可选依赖。请运行：pipx install 'pathpilot\\[gui]'。",
        "The optional GUI dependencies are not installed. Run: pipx install 'pathpilot\\[gui]'.",
    ),
    "root_reason_custom": ("使用用户自定义根目录", "Using the user-configured root"),
    "root_reason_isolated": ("PATHPILOT_HOME 隔离运行时根目录", "Using the PATHPILOT_HOME isolated runtime root"),
    "root_reason_non_system": ("自动选择剩余空间最大的非系统盘", "Automatically selected the non-system drive with the most free space"),
    "root_reason_system_fallback": ("未找到合适的非系统盘，退回系统盘", "No suitable non-system drive was found; using the system drive"),
    "legacy_reason": (
        "旧版 command-only 记录不可信；必须重新生成建议。",
        "Legacy command-only records are unsafe; regenerate the suggestion.",
    ),
}


@dataclass
class RuntimeContext:
    lang: str = "zh"


ctx = RuntimeContext()


def normalize_lang(lang: str | None) -> str:
    value = (lang or "zh").lower().strip()
    if value not in SUPPORTED_LANGS:
        return "zh"
    return value


def set_lang(lang: str | None) -> None:
    ctx.lang = normalize_lang(lang)


def get_lang() -> str:
    return ctx.lang


def text(zh: str, en: str, lang: str | None = None) -> str:
    active_lang = normalize_lang(lang or ctx.lang)
    if active_lang == "en":
        return en
    if active_lang == "bi":
        return f"{zh} / {en}"
    return zh


def message(key: str, lang: str | None = None, **values: object) -> str:
    zh, en = MESSAGES[key]
    return text(zh.format(**values), en.format(**values), lang)


def cell_text(zh: str, en: str, lang: str | None = None) -> str:
    active_lang = normalize_lang(lang or ctx.lang)
    if active_lang == "en":
        return en
    if active_lang == "bi":
        return f"{zh}\n{en}"
    return zh


def title_text(zh: str, en: str, lang: str | None = None) -> str:
    return text(zh, en, lang)


def status_text(status_key: str, lang: str | None = None) -> str:
    mapping = {
        "ok": ("正常", "OK"),
        "missing": ("缺失", "Missing"),
        "changed": ("有变更", "Changed"),
        "clean": ("干净", "Clean"),
        "warning": ("警告", "Warning"),
        "unknown": ("未知", "Unknown"),
        "cancelled": ("已取消", "Cancelled"),
        "failed": ("失败", "Failed"),
        "success": ("成功", "Success"),
        "pending": ("待处理", "Pending"),
        "launched": ("已启动", "Launched"),
        "launch_failed": ("启动失败", "Launch failed"),
        "blocked": ("已阻止", "Blocked"),
        "legacy_unsafe": ("旧版不安全", "Legacy unsafe"),
        "skipped": ("已跳过", "Skipped"),
    }
    zh, en = mapping.get(status_key, (status_key, status_key))
    return cell_text(zh, en, lang)
