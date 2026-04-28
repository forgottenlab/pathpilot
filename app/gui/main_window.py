from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QTabWidget,
    QHBoxLayout, QPushButton
)

from app.installers.queue import get_pending_items
from app.gui.install_page import InstallPage
from app.gui.settings_page import SettingsPage
from app.gui.ui_helpers import open_in_explorer
from app.core.settings import load_settings


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PathPilot")
        self.resize(1280, 820)

        self.settings = load_settings()
        self.runtime_paths = self.settings["runtime_paths"]

        central = QWidget()
        layout = QVBoxLayout(central)

        top_bar = QHBoxLayout()

        self.status_label = QLabel()
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 600;
                padding: 4px 0;
            }
        """)

        self.refresh_status_btn = QPushButton("刷新状态")
        self.refresh_status_btn.clicked.connect(self.refresh_status)

        self.open_root_btn = QPushButton("打开根目录")
        self.open_root_btn.clicked.connect(lambda: open_in_explorer(self.runtime_paths["root_dir"]))

        self.open_incoming_btn = QPushButton("打开 Incoming")
        self.open_incoming_btn.clicked.connect(lambda: open_in_explorer(self.runtime_paths["incoming_root"]))

        top_bar.addWidget(self.status_label, 1)
        top_bar.addWidget(self.refresh_status_btn)
        top_bar.addWidget(self.open_root_btn)
        top_bar.addWidget(self.open_incoming_btn)

        self.tabs = QTabWidget()
        self.install_page = InstallPage()
        self.settings_page = SettingsPage()

        self.tabs.addTab(self.install_page, "待安装建议")
        self.tabs.addTab(self.settings_page, "设置")

        layout.addLayout(top_bar)
        layout.addWidget(self.tabs)

        self.setCentralWidget(central)
        self.refresh_status()

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #202124;
                color: #f1f3f4;
                font-size: 14px;
            }
            QTabWidget::pane {
                border: 1px solid #3a3a3a;
                border-radius: 10px;
                background: #26282c;
            }
            QTabBar::tab {
                background: #2e3136;
                color: #f1f3f4;
                padding: 10px 18px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: #3a3f45;
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
        """)

    def refresh_status(self) -> None:
        self.settings = load_settings()
        self.runtime_paths = self.settings["runtime_paths"]
        pending_count = len(get_pending_items())

        self.status_label.setText(
            f"根目录：{self.runtime_paths['root_dir']}    |    "
            f"Incoming：{self.runtime_paths['incoming_root']}    |    "
            f"待处理建议：{pending_count}"
        )
