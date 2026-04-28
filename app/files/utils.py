from __future__ import annotations

import time
from pathlib import Path


def is_hidden(path: Path) -> bool:
    return path.name.startswith(".")


def wait_until_file_stable(path: Path, stable_seconds: int = 2, checks: int = 3) -> bool:
    """
    等待文件写入稳定，避免浏览器还没下载完就移动。
    """
    try:
        previous_size = -1
        stable_count = 0

        for _ in range(checks * 3):
            if not path.exists() or not path.is_file():
                return False

            current_size = path.stat().st_size
            if current_size == previous_size:
                stable_count += 1
            else:
                stable_count = 0

            if stable_count >= checks:
                return True

            previous_size = current_size
            time.sleep(stable_seconds)

        return False
    except OSError:
        return False


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
