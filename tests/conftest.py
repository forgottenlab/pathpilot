from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PATHPILOT_HOME"] = str(
    Path(tempfile.gettempdir()) / "pathpilot-pytest-collection-home"
)


@pytest.fixture(autouse=True)
def isolated_pathpilot_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "pathpilot-home"
    monkeypatch.setenv("PATHPILOT_HOME", str(home))
    return home


@pytest.fixture
def runtime_paths(tmp_path: Path) -> dict[str, str]:
    root = tmp_path / "managed-root"
    return {
        "root_dir": str(root),
        "archive_root": str(root / "Downloads"),
        "apps_root": str(root / "Apps"),
        "data_root": str(root / "Data"),
        "incoming_root": str(root / "Downloads" / "00-Incoming"),
        "user_downloads": str(tmp_path / "User Downloads"),
    }


def pytest_sessionfinish(session, exitstatus) -> None:
    """Close leftover Qt widgets before interpreter shutdown."""
    # PySide6 6.12 on Windows can access-violate after a passing
    # session if QApplication still owns widgets at process exit.
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return
    app = QApplication.instance()
    if app is None:
        return
    for widget in list(app.allWidgets()):
        widget.hide()
        widget.close()
        widget.deleteLater()
    app.processEvents()
    import gc
    gc.collect()
    app.processEvents()
