from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication

from app.gui.main_window import MainWindow


def create_main_window() -> tuple[QApplication, MainWindow]:
    """Create the GUI for smoke tests and the CLI launcher."""
    app = QApplication.instance() or QApplication(sys.argv)
    return app, MainWindow()


def main() -> None:
    """Internal GUI launcher used by the canonical ``pathpilot ui`` command."""
    app, window = create_main_window()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
