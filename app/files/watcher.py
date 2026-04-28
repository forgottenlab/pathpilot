from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.files.classifier import classify_file
from app.installers.queue import add_install_suggestion
from app.installers.detector import (
    detect_installer_family,
    get_family_rule,
    load_installer_rules,
    match_known_app,
)
from app.installers.runner import log_install_suggestion
from app.installers.strategy import (
    build_suggestion_from_family,
    build_suggestion_from_known_app,
)
from app.core.logger import log
from app.files.mover import move_file
from app.files.utils import ensure_dir, is_hidden, wait_until_file_stable


TEMP_SUFFIXES = {".crdownload", ".tmp", ".part", ".download"}


class DownloadEventHandler(FileSystemEventHandler):
    def __init__(self, settings: dict[str, Any], rules: dict[str, Any]) -> None:
        super().__init__()
        self.settings = settings
        self.rules = rules
        self.runtime_paths = settings["runtime_paths"]
        self.behavior = settings["behavior"]
        self.incoming_root = Path(self.runtime_paths["incoming_root"]).resolve()

        self.recently_processed: dict[str, float] = {}
        self.dedup_window_seconds = 3.0

        self.installers_incoming_dir = Path(
            f"{self.runtime_paths['archive_root']}/01-Software/_IncomingInstallers"
        ).resolve()

        self.installer_rules = load_installer_rules()

    def on_created(self, event) -> None:
        if event.is_directory:
            return
        self._handle_file(Path(event.src_path))

    def on_moved(self, event) -> None:
        if event.is_directory:
            return
        self._handle_file(Path(event.dest_path))

    def _normalize_key(self, path: Path) -> str:
        try:
            return str(path.resolve()).lower()
        except Exception:
            return str(path).lower()

    def _should_skip_recent(self, path: Path) -> bool:
        now = time.time()
        key = self._normalize_key(path)

        expired_keys = [
            k for k, ts in self.recently_processed.items()
            if now - ts > self.dedup_window_seconds
        ]
        for k in expired_keys:
            self.recently_processed.pop(k, None)

        last_ts = self.recently_processed.get(key)
        if last_ts is not None and now - last_ts <= self.dedup_window_seconds:
            return True

        self.recently_processed[key] = now
        return False

    def _try_handle_installer(self, file_path: Path) -> None:
        try:
            if file_path.parent.resolve() != self.installers_incoming_dir:
                return

            if file_path.suffix.lower() not in {".exe", ".msi"}:
                return

            known_rule = match_known_app(file_path, self.installer_rules)
            if known_rule:
                suggestion = build_suggestion_from_known_app(
                    file_path=file_path,
                    known_rule=known_rule,
                    runtime_paths=self.runtime_paths
                )
            else:
                family = detect_installer_family(file_path)
                family_rule = get_family_rule(family, self.installer_rules)

                if not family_rule:
                    log(f"未找到安装器家族规则，仅归档保留: {file_path}")
                    return

                suggestion = build_suggestion_from_family(
                    file_path=file_path,
                    family_rule=family_rule,
                    runtime_paths=self.runtime_paths
                )

            record = add_install_suggestion(suggestion)
            log_install_suggestion(record)

        except Exception as e:
            log(f"安装器建议处理失败: {file_path} | 错误: {e}")

    def _handle_file(self, file_path: Path) -> None:
        try:
            if not file_path.exists() or not file_path.is_file():
                return

            if file_path.suffix.lower() in TEMP_SUFFIXES:
                return

            if self.behavior.get("ignore_hidden_files", True) and is_hidden(file_path):
                return

            if self._should_skip_recent(file_path):
                log(f"跳过短时间重复事件: {file_path}")
                return

            stable_seconds = int(self.behavior.get("stable_check_seconds", 2))
            stable_checks = int(self.behavior.get("stable_checks", 3))

            if not wait_until_file_stable(
                file_path,
                stable_seconds=stable_seconds,
                checks=stable_checks
            ):
                log(f"跳过不稳定文件: {file_path}")
                return

            current_parent = file_path.parent.resolve()

            if current_parent != self.incoming_root:
                ensure_dir(self.incoming_root)
                new_path = move_file(file_path, self.incoming_root)
                log(f"已收口到 Incoming: {file_path} -> {new_path}")
                return

            target_dir = classify_file(file_path, self.rules, self.runtime_paths)
            ensure_dir(target_dir)

            if current_parent == target_dir.resolve():
                log(f"文件已在目标目录，跳过: {file_path}")
                return

            new_path = move_file(file_path, target_dir)
            log(f"已二次分类: {file_path} -> {new_path}")

            self._try_handle_installer(new_path)

        except Exception as e:
            log(f"处理失败: {file_path} | 错误: {e}")


def start_watching(settings: dict[str, Any], rules: dict[str, Any]) -> None:
    observer = Observer()
    handler = DownloadEventHandler(settings, rules)

    watch_dirs = settings.get("watch_directories", [])
    for directory in watch_dirs:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        observer.schedule(handler, str(path), recursive=False)
        log(f"开始监听目录: {path}")

    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("收到退出信号，正在停止监听...")
        observer.stop()

    observer.join()
