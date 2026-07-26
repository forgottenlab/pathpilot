from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable


class PathPolicyError(ValueError):
    def __init__(self, zh: str, en: str) -> None:
        super().__init__(en)
        self.zh = zh
        self.en = en

    def localized(self, lang: str = "zh") -> str:
        if lang == "en":
            return self.en
        if lang == "bi":
            return f"{self.zh} / {self.en}"
        return self.zh


def normalize_path(path: str | os.PathLike[str]) -> Path:
    raw = os.path.expandvars(str(path).strip())
    if not raw:
        raise PathPolicyError("路径不能为空。", "Path cannot be empty.")
    return Path(raw).expanduser().resolve(strict=False)


def _path_key(path: str | os.PathLike[str]) -> str:
    resolved = normalize_path(path)
    value = os.path.normcase(os.path.normpath(str(resolved)))
    anchor = os.path.normcase(os.path.normpath(resolved.anchor)) if resolved.anchor else ""
    return anchor if anchor and value == anchor else value.rstrip("\\/")


def _is_same_or_child(path: str | os.PathLike[str], parent: str | os.PathLike[str]) -> bool:
    path_key = _path_key(path)
    parent_key = _path_key(parent)
    try:
        return os.path.commonpath([path_key, parent_key]) == parent_key
    except ValueError:
        return False


def paths_overlap(
    first: str | os.PathLike[str],
    second: str | os.PathLike[str],
) -> bool:
    return _is_same_or_child(first, second) or _is_same_or_child(second, first)


def _is_drive_root(path: str | os.PathLike[str]) -> bool:
    resolved = normalize_path(path)
    return bool(resolved.anchor) and _path_key(resolved) == _path_key(resolved.anchor)


def _protected_roots() -> list[Path]:
    candidates = [
        os.environ.get("SystemRoot", r"C:\Windows"),
        os.environ.get("WINDIR", r"C:\Windows"),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("ProgramData", r"C:\ProgramData"),
        os.environ.get("PATHPILOT_HOME", str(Path.home() / ".pathpilot")),
        str(Path.home() / ".pathpilot"),
    ]
    roots: list[Path] = []
    for candidate in candidates:
        if candidate:
            roots.append(normalize_path(candidate))
    return roots


def is_protected_path(path: str | os.PathLike[str]) -> bool:
    resolved = normalize_path(path)
    return _is_drive_root(resolved) or any(
        _is_same_or_child(resolved, protected)
        for protected in _protected_roots()
    )


def validate_root_directory(
    path: str | os.PathLike[str],
    source_directories: Iterable[str | os.PathLike[str]] = (),
) -> Path:
    resolved = normalize_path(path)
    if is_protected_path(resolved):
        raise PathPolicyError(
            f"PathPilot 根目录位于受保护位置: {resolved}",
            f"The PathPilot root is in a protected location: {resolved}",
        )
    for source in source_directories:
        if paths_overlap(resolved, source):
            raise PathPolicyError(
                f"PathPilot 根目录与监听来源重叠: {resolved} <-> {normalize_path(source)}",
                f"The PathPilot root overlaps a source directory: {resolved} <-> {normalize_path(source)}",
            )
    return resolved


def validate_source_directory(
    path: str | os.PathLike[str],
    runtime_paths: dict[str, Any],
    *,
    allow_internal_incoming: bool = False,
) -> Path:
    resolved = normalize_path(path)
    incoming = normalize_path(runtime_paths["incoming_root"])
    if allow_internal_incoming and _path_key(resolved) == _path_key(incoming):
        return resolved

    if is_protected_path(resolved):
        raise PathPolicyError(
            f"监听来源位于受保护位置: {resolved}",
            f"The source directory is in a protected location: {resolved}",
        )

    managed_roots = [
        runtime_paths["root_dir"],
        runtime_paths["archive_root"],
        runtime_paths["apps_root"],
        runtime_paths["data_root"],
        runtime_paths["incoming_root"],
    ]
    for managed in managed_roots:
        if paths_overlap(resolved, managed):
            raise PathPolicyError(
                f"监听来源不得与 PathPilot 受管目录重叠: {resolved}",
                f"The source directory must not overlap PathPilot-managed paths: {resolved}",
            )
    return resolved


def validate_install_target(
    path: str | os.PathLike[str],
    apps_root: str | os.PathLike[str],
) -> Path:
    resolved = normalize_path(path)
    resolved_apps = normalize_path(apps_root)
    if is_protected_path(resolved):
        raise PathPolicyError(
            f"安装目标位于受保护位置: {resolved}",
            f"The installation target is in a protected location: {resolved}",
        )
    if _path_key(resolved) == _path_key(resolved_apps) or not _is_same_or_child(resolved, resolved_apps):
        raise PathPolicyError(
            f"安装目标必须是 Apps 根目录下的子目录: {resolved}",
            f"The installation target must be a child of the Apps root: {resolved}",
        )
    return resolved


def validate_installer_path(
    path: str | os.PathLike[str],
    installers_root: str | os.PathLike[str],
) -> Path:
    resolved = normalize_path(path)
    resolved_root = normalize_path(installers_root)
    if not _is_same_or_child(resolved, resolved_root) or _path_key(resolved) == _path_key(resolved_root):
        raise PathPolicyError(
            f"安装包必须位于 PathPilot 受管安装包目录内: {resolved}",
            f"The installer must be inside PathPilot's managed installer directory: {resolved}",
        )
    if resolved.suffix.lower() not in {".exe", ".msi"}:
        raise PathPolicyError(
            f"不支持的安装包类型: {resolved}",
            f"Unsupported installer type: {resolved}",
        )
    if not resolved.exists() or not resolved.is_file():
        raise PathPolicyError(
            f"安装包不存在或不是普通文件: {resolved}",
            f"The installer does not exist or is not a regular file: {resolved}",
        )
    return resolved


def resolve_configured_sources(
    settings: dict[str, Any],
    runtime_paths: dict[str, Any],
) -> list[Path]:
    configured = settings.get("watch_directories", ["{user_downloads}"])
    sources: list[Path] = []
    for value in configured:
        try:
            rendered = str(value).format(**runtime_paths)
        except (KeyError, ValueError) as exc:
            raise PathPolicyError(
                f"监听来源模板无效: {value}",
                f"Invalid source directory template: {value}",
            ) from exc
        sources.append(normalize_path(rendered))
    return sources


def validate_runtime_layout(
    settings: dict[str, Any],
    runtime_paths: dict[str, Any],
) -> list[Path]:
    sources = resolve_configured_sources(settings, runtime_paths)
    validate_root_directory(runtime_paths["root_dir"], sources)
    for source in sources:
        validate_source_directory(source, runtime_paths)
    return sources
