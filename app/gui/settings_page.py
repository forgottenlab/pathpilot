from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
)

from app.gui.ui_helpers import load_json_file, save_json_file
from app.core.json_store import JsonStoreError, ensure_json_file
from app.core.path_policy import PathPolicyError, normalize_path, validate_runtime_layout
from app.core.paths import DEFAULT_SETTINGS, get_settings_path
from app.core.settings import build_runtime_paths


class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.settings_path = get_settings_path()
        try:
            ensure_json_file(self.settings_path, DEFAULT_SETTINGS, expected_type=dict)
        except JsonStoreError:
            pass

        self._build_ui()
        self.load_current_settings()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("设置")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        layout.addWidget(QLabel("PathPilot 根目录"))
        self.root_dir_edit = QLineEdit()
        self.root_dir_edit.setPlaceholderText("留空表示自动选择非系统盘中剩余空间最大的盘")
        layout.addWidget(self.root_dir_edit)

        self.choose_root_btn = QPushButton("选择根目录")
        self.choose_root_btn.clicked.connect(self.choose_root_dir)
        layout.addWidget(self.choose_root_btn)

        layout.addWidget(QLabel("监听目录（多个用分号 ; 分隔）"))
        self.watch_dirs_edit = QLineEdit()
        self.watch_dirs_edit.setPlaceholderText("{user_downloads};D:/OtherDownloadFolder")
        layout.addWidget(self.watch_dirs_edit)

        self.save_btn = QPushButton("保存设置")
        self.save_btn.clicked.connect(self.save_settings)
        layout.addWidget(self.save_btn)

        layout.addWidget(QLabel("说明：保存后需要重启 PathPilot watcher 或重新打开 GUI 才会完全生效。"))
        layout.addStretch()

        self.setStyleSheet("""
            QPushButton {
                background: #3a3a3a;
                border: 1px solid #4a4a4a;
                border-radius: 8px;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background: #4a4a4a;
            }
            QLineEdit {
                border: 1px solid #4a4a4a;
                border-radius: 8px;
                padding: 8px;
                background: #252525;
            }
            QLabel {
                padding: 2px;
            }
        """)

    def load_current_settings(self) -> None:
        try:
            ensure_json_file(self.settings_path, DEFAULT_SETTINGS, expected_type=dict)
            settings = load_json_file(self.settings_path)
        except JsonStoreError as exc:
            QMessageBox.critical(self, "配置文件错误", str(exc))
            return

        base_paths = settings.get("base_paths", {})
        watch_dirs = settings.get("watch_directories", [])

        self.root_dir_edit.setText(base_paths.get("root_dir", ""))
        self.watch_dirs_edit.setText(";".join(watch_dirs))

    def choose_root_dir(self) -> None:
        current = self.root_dir_edit.text().strip() or "C:/"
        chosen = QFileDialog.getExistingDirectory(self, "选择 PathPilot 根目录", current)

        if chosen:
            self.root_dir_edit.setText(chosen.replace("\\", "/"))

    def save_settings(self) -> None:
        try:
            ensure_json_file(self.settings_path, DEFAULT_SETTINGS, expected_type=dict)
            settings = load_json_file(self.settings_path)
        except JsonStoreError as exc:
            QMessageBox.critical(self, "配置文件错误", str(exc))
            return

        if not isinstance(settings, dict):
            settings = {}

        settings.setdefault("base_paths", {})
        settings.setdefault("behavior", {
            "ignore_hidden_files": True,
            "stable_check_seconds": 2,
            "stable_checks": 3,
            "create_missing_dirs": True,
            "overwrite_strategy": "rename"
        })

        root_dir = self.root_dir_edit.text().strip()
        watch_dirs = [
            item.strip().replace("\\", "/")
            for item in self.watch_dirs_edit.text().split(";")
            if item.strip()
        ]

        if not watch_dirs:
            watch_dirs = ["{user_downloads}"]

        settings["base_paths"]["root_dir"] = root_dir
        settings["watch_directories"] = watch_dirs

        try:
            runtime_paths = build_runtime_paths(settings)
            validated_sources = validate_runtime_layout(settings, runtime_paths)
        except PathPolicyError as exc:
            QMessageBox.warning(self, "路径不安全", exc.localized("zh"))
            return

        if root_dir:
            settings["base_paths"]["root_dir"] = str(
                normalize_path(runtime_paths["root_dir"])
            ).replace("\\", "/")
        settings["watch_directories"] = [
            original if "{" in original else str(validated).replace("\\", "/")
            for original, validated in zip(watch_dirs, validated_sources)
        ]

        try:
            save_json_file(self.settings_path, settings)
        except JsonStoreError as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return

        QMessageBox.information(
            self,
            "成功",
            "设置已保存。\n重启 PathPilot watcher 或重新打开 GUI 后完全生效。"
        )
