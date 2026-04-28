from __future__ import annotations

from datetime import datetime

from app.core.paths import LOG_DIR, ensure_user_config_files


def log(message: str) -> None:
    ensure_user_config_files()
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / "pathpilot.log"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
