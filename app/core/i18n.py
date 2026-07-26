from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_LANGS = {"zh", "en", "bi"}


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
