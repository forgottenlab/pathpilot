from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QLineEdit, QFileDialog, QMessageBox, QHeaderView,
    QFrame
)

from app.installers.queue import (
    get_pending_items,
    load_pending_installs,
    update_install_suggestion_status,
)
from app.installers.runner import run_install_record
from app.gui.ui_helpers import open_in_explorer, normalize_display_name


class InstallPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.current_record: dict | None = None
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
        right.addWidget(self.target_edit)

        self.browse_btn = QPushButton("选择自定义目录")
        self.browse_btn.clicked.connect(self.choose_target_dir)
        right.addWidget(self.browse_btn)

        right.addWidget(QLabel("建议命令"))
        self.command_edit = QLineEdit()
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
        items = get_pending_items()
        self.summary_label.setText(f"待处理安装建议：{len(items)}")
        self.table.setRowCount(len(items))

        selected_row = None

        for row, item in enumerate(items):
            display_name = normalize_display_name(item["name"])
            values = [
                str(item["id"]),
                display_name,
                item["source"],
                item["family"],
                item["mode"],
                item["status"],
            ]

            for col, value in enumerate(values):
                table_item = QTableWidgetItem(value)
                if col == 0:
                    table_item.setData(Qt.UserRole, item)

                # 模式着色
                if item["mode"] == "auto":
                    table_item.setForeground(QColor("#86d993"))
                elif item["mode"] == "try":
                    table_item.setForeground(QColor("#f1c56b"))
                elif item["mode"] == "suggest":
                    table_item.setForeground(QColor("#8ab4f8"))

                self.table.setItem(row, col, table_item)

            if keep_id is not None and int(item["id"]) == keep_id:
                selected_row = row

        if items:
            if selected_row is not None:
                self.table.selectRow(selected_row)
            elif not silent:
                self.table.selectRow(0)
        else:
            self.current_record = None
            self.clear_detail()

    def clear_detail(self) -> None:
        self.name_label.setText("名称：-")
        self.source_label.setText("来源：-")
        self.family_label.setText("家族：-")
        self.mode_label.setText("模式：-")
        self.installer_label.setText("安装包：-")
        self.target_edit.setText("")
        self.command_edit.setText("")

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

        self.current_record = record

        self.name_label.setText(f"名称：{normalize_display_name(record['name'])}")
        self.source_label.setText(f"来源：{record['source']}")
        self.family_label.setText(f"家族：{record['family']}")
        self.mode_label.setText(f"模式：{record['mode']}")
        self.installer_label.setText(f"安装包：{record['installer']}")
        self.target_edit.setText(record["target"])
        self.command_edit.setText(record["command"])

    def choose_target_dir(self) -> None:
        if not self.current_record:
            return

        current_target = self.target_edit.text().strip()
        chosen = QFileDialog.getExistingDirectory(self, "选择安装目录", current_target)
        if not chosen:
            return

        chosen = chosen.replace("\\", "/")
        self.target_edit.setText(chosen)

        installer = self.current_record["installer"]
        old_target = self.current_record["target"]
        command = self.current_record["command"].replace(old_target, chosen)
        self.command_edit.setText(command)

    def run_current_record(self) -> None:
        if not self.current_record:
            return

        mode = self.current_record["mode"]
        if mode == "suggest":
            QMessageBox.information(self, "提示", "当前建议为 suggest 模式，默认不自动执行。")
            return

        items = load_pending_installs()
        target_id = int(self.current_record["id"])
        record = next((x for x in items if int(x["id"]) == target_id), None)
        if not record:
            QMessageBox.warning(self, "错误", "未找到该安装建议。")
            return

        record["target"] = self.target_edit.text().strip()
        record["command"] = self.command_edit.text().strip()

        ok = run_install_record(record)
        if ok:
            QMessageBox.information(self, "成功", "安装命令已启动。")
            self.refresh_table()
        else:
            QMessageBox.warning(self, "失败", "安装命令启动失败。")

    def skip_current_record(self) -> None:
        if not self.current_record:
            return

        update_install_suggestion_status(int(self.current_record["id"]), "skipped")
        QMessageBox.information(self, "完成", "已跳过该安装建议。")
        self.refresh_table()

    def open_installer_location(self) -> None:
        if not self.current_record:
            return
        open_in_explorer(self.current_record["installer"])

    def open_target_location(self) -> None:
        if not self.current_record:
            return
        open_in_explorer(self.target_edit.text().strip())
