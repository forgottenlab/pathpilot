from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PATHPILOT_HOME"] = str(
    Path.cwd() / "data" / "pytest-collection-home"
)


@pytest.fixture(autouse=True)
def isolated_pathpilot_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "pathpilot-home"
    monkeypatch.setenv("PATHPILOT_HOME", str(home))

    import app.core.paths as paths

    monkeypatch.setattr(paths, "APP_HOME", home)
    monkeypatch.setattr(paths, "CONFIG_DIR", home / "config")
    monkeypatch.setattr(paths, "DATA_DIR", home / "data")
    monkeypatch.setattr(paths, "LOG_DIR", home / "data" / "logs")

    logger = sys.modules.get("app.core.logger")
    if logger is not None:
        monkeypatch.setattr(logger, "LOG_DIR", paths.LOG_DIR)
    cli = sys.modules.get("app.cli")
    if cli is not None:
        monkeypatch.setattr(cli, "SETTINGS_FILE", paths.CONFIG_DIR / "settings.json")
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
