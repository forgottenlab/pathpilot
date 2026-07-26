from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QLineEdit, QFileDialog, QMessageBox, QHeaderView,
    QFrame
)

from app.core.path_policy import PathPolicyError, validate_install_target
from app.core.settings import load_settings
from app.installers.queue import (
    load_pending_installs,
    update_install_suggestion_status,
)
from app.installers.runner import run_install_record
from app.installers.strategy import rebuild_execution_fields
from app.gui.ui_helpers import open_in_explorer, normalize_display_name


class InstallPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.current_record: dict | None = None
        self._target_dirty = False
        self._build_ui()
        self._setup_timer()
        self.refresh_table()

    def _setup_timer(self) -> None:
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_table_silent)
        self.timer.start(2000)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        self.summary_label = QLabel("待处理安装建议：0")
        self.summary_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 600;
                padding: 4px 0;
            }
        """)
        root.addWidget(self.summary_label)

        body = QHBoxLayout()

        # 左侧列表区
        left = QVBoxLayout()
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "ID", "名称", "来源", "家族", "模式", "状态"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_table)

        left.addWidget(QLabel("待处理安装建议"))
        left.addWidget(self.table)
        left.addWidget(self.refresh_btn)

        # 右侧详情区
        right = QVBoxLayout()
        right.setSpacing(10)

        title = QLabel("详情")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        right.addWidget(title)

        self.name_label = QLabel("名称：-")
        self.source_label = QLabel("来源：-")
        self.family_label = QLabel("家族：-")
        self.mode_label = QLabel("模式：-")
        self.installer_label = QLabel("安装包：-")
        self.installer_label.setWordWrap(True)

        right.addWidget(self.name_label)
        right.addWidget(self.source_label)
        right.addWidget(self.family_label)
        right.addWidget(self.mode_label)
        right.addWidget(self.installer_label)

        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        right.addWidget(line1)

        right.addWidget(QLabel("安装目录"))
        self.target_edit = QLineEdit()
        self.target_edit.textEdited.connect(self.on_target_edited)
        right.addWidget(self.target_edit)

        self.browse_btn = QPushButton("选择自定义目录")
        self.browse_btn.clicked.connect(self.choose_target_dir)
        right.addWidget(self.browse_btn)

        right.addWidget(QLabel("建议命令"))
        self.command_edit = QLineEdit()
        self.command_edit.setReadOnly(True)
        self.command_edit.setToolTip("仅供预览；该文本不会作为 shell 命令执行。")
        right.addWidget(self.command_edit)

        self.run_recommended_btn = QPushButton("使用当前目录安装")
        self.run_recommended_btn.clicked.connect(self.run_current_record)

        self.skip_btn = QPushButton("跳过")
        self.skip_btn.clicked.connect(self.skip_current_record)

        self.open_installer_btn = QPushButton("打开安装包位置")
        self.open_installer_btn.clicked.connect(self.open_installer_location)

        self.open_target_btn = QPushButton("打开目标目录")
        self.open_target_btn.clicked.connect(self.open_target_location)

        for btn in [
            self.run_recommended_btn,
            self.skip_btn,
            self.open_installer_btn,
            self.open_target_btn
        ]:
            btn.setMinimumHeight(36)
            right.addWidget(btn)

        right.addStretch()

        body.addLayout(left, 3)
        body.addLayout(right, 2)
        root.addLayout(body)

        self.setStyleSheet("""
            QTableWidget {
                gridline-color: #3a3a3a;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                background: #252525;
                alternate-background-color: #2b2b2b;
            }
            QHeaderView::section {
                background: #333333;
                padding: 6px;
                border: none;
                font-weight: 600;
            }
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
        """)

    def refresh_table_silent(self) -> None:
        current_id = None
        if self.current_record:
            current_id = int(self.current_record["id"])
        self.refresh_table(keep_id=current_id, silent=True)

    def refresh_table(self, keep_id: int | None = None, silent: bool = False) -> None:
        items = [
            item for item in load_pending_installs()
            if item.get("status") in {"pending", "legacy_unsafe"}
        ]
        self.summary_label.setText(f"待处理安装建议：{len(items)}")
        preserve_dirty = bool(silent and self._target_dirty and self.current_record)
        preserved_id = int(self.current_record["id"]) if preserve_dirty else None
        preserved_target = self.target_edit.text() if preserve_dirty else ""

        self.table.blockSignals(True)
        self.table.setRowCount(len(items))

        selected_row = None

        for row, item in enumerate(items):
            display_name = normalize_display_name(item.get("name", ""))
            values = [
                str(item.get("id", "")),
                display_name,
                item.get("source", "legacy"),
                item.get("installer_family", item.get("family", "unknown")),
                item.get("mode", "suggest"),
                item.get("status", "legacy_unsafe"),
            ]

            for col, value in enumerate(values):
                table_item = QTableWidgetItem(value)
                if col == 0:
                    table_item.setData(Qt.UserRole, item)

                if item.get("mode", "suggest") == "suggest":
                    table_item.setForeground(QColor("#8ab4f8"))

                self.table.setItem(row, col, table_item)

            if keep_id is not None and int(item["id"]) == keep_id:
                selected_row = row

        if items:
            if selected_row is not None:
                self.table.selectRow(selected_row)
            elif not silent:
                selected_row = 0
                self.table.selectRow(0)
        else:
            self.current_record = None
            self.clear_detail()
        self.table.blockSignals(False)

        if selected_row is not None:
            record = items[selected_row]
            keep_edit = preserved_id == int(record["id"])
            self.show_record(record, preserve_target=preserved_target if keep_edit else None)

    def clear_detail(self) -> None:
        self.name_label.setText("名称：-")
        self.source_label.setText("来源：-")
        self.family_label.setText("家族：-")
        self.mode_label.setText("模式：-")
        self.installer_label.setText("安装包：-")
        self.target_edit.setText("")
        self.command_edit.setText("")
        self.run_recommended_btn.setEnabled(False)
        self._target_dirty = False

    def on_selection_changed(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            self.current_record = None
            self.clear_detail()
            return

        item = self.table.item(row, 0)
        if item is None:
            self.current_record = None
            self.clear_detail()
            return

        record = item.data(Qt.UserRole)
        if not record:
            self.current_record = None
            self.clear_detail()
            return

        preserve = self.target_edit.text() if (
            self._target_dirty
            and self.current_record
            and int(self.current_record["id"]) == int(record["id"])
        ) else None
        self.show_record(record, preserve_target=preserve)

    def show_record(self, record: dict, preserve_target: str | None = None) -> None:
        self.current_record = record
        self.name_label.setText(f"名称：{normalize_display_name(record.get('name', ''))}")
        self.source_label.setText(f"来源：{record.get('source', 'legacy')}")
        self.family_label.setText(
            f"家族：{record.get('installer_family', record.get('family', '-'))}"
        )
        self.mode_label.setText(f"模式：{record.get('mode', '-')}")
        self.installer_label.setText(
            f"安装包：{record.get('installer_path', record.get('installer', '-'))}"
        )
        is_legacy = record.get("status") == "legacy_unsafe" or "executable" not in record
        self.run_recommended_btn.setEnabled(not is_legacy)
        if preserve_target is None:
            self.target_edit.setText(record.get("target_dir", record.get("target", "")))
            self._target_dirty = False
        else:
            self.target_edit.setText(preserve_target)
            self._target_dirty = True
        if is_legacy:
            self.command_edit.setText(
                record.get("legacy_preview", "旧版 command-only 记录；请重新生成建议。")
            )
        else:
            self.update_preview()

    def on_target_edited(self, _value: str) -> None:
        self._target_dirty = True
        self.update_preview()

    def update_preview(self) -> None:
        if not self.current_record or "executable" not in self.current_record:
            return
        try:
            fields = rebuild_execution_fields(
                self.current_record,
                self.target_edit.text().strip(),
            )
        except (KeyError, TypeError, ValueError):
            self.command_edit.setText("目标目录无效")
            return
        self.command_edit.setText(fields["preview"])

    def choose_target_dir(self) -> None:
        if not self.current_record:
            return

        current_target = self.target_edit.text().strip()
        chosen = QFileDialog.getExistingDirectory(self, "选择安装目录", current_target)
        if not chosen:
            return

        chosen = chosen.replace("\\", "/")
        self.target_edit.setText(chosen)
        self._target_dirty = True
        self.update_preview()

    def run_current_record(self) -> None:
        if not self.current_record:
            return

        if self.current_record.get("status") == "legacy_unsafe" or "executable" not in self.current_record:
            QMessageBox.warning(self, "已阻止", "旧版 command-only 记录不允许执行，请重新生成建议。")
            return

        if self.current_record.get("mode") == "suggest":
            answer = QMessageBox.question(
                self,
                "确认启动",
                "所有安装建议都需要显式确认。是否使用当前目标目录启动安装器？\n"
                "启动进程不表示安装成功。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        items = load_pending_installs()
        target_id = int(self.current_record["id"])
        record = next((x for x in items if int(x["id"]) == target_id), None)
        if not record:
            QMessageBox.warning(self, "错误", "未找到该安装建议。")
            return

        if record.get("status") != "pending" or "executable" not in record:
            QMessageBox.warning(self, "已阻止", "建议状态或结构已变化，请刷新后重试。")
            return

        try:
            settings = load_settings()
            runtime_paths = settings["runtime_paths"]
            apps_root = runtime_paths["apps_root"]
            installers_root = str(
                Path(runtime_paths["archive_root"])
                / "01-Software"
                / "_IncomingInstallers"
            )
            target = validate_install_target(self.target_edit.text().strip(), apps_root)
        except PathPolicyError as exc:
            QMessageBox.warning(self, "路径不安全", exc.localized("zh"))
            return

        ok = run_install_record(
            record,
            apps_root=apps_root,
            installers_root=installers_root,
            target_dir=target,
        )
        if ok:
            self._target_dirty = False
            QMessageBox.information(self, "已启动", "安装器进程已启动；这不代表安装成功。")
            self.refresh_table()
        else:
            QMessageBox.warning(self, "失败", "安装器启动失败或被安全策略阻止。")

    def skip_current_record(self) -> None:
        if not self.current_record:
            return

        update_install_suggestion_status(int(self.current_record["id"]), "skipped")
        QMessageBox.information(self, "完成", "已跳过该安装建议。")
        self.refresh_table()

    def open_installer_location(self) -> None:
        if not self.current_record:
            return
        open_in_explorer(
            self.current_record.get("installer_path", self.current_record.get("installer", ""))
        )

    def open_target_location(self) -> None:
        if not self.current_record:
            return
        open_in_explorer(self.target_edit.text().strip())
