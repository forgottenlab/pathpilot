from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.logger import log


def log_scan_summary(results: list[dict[str, Any]]) -> None:
    if not results:
        log("安装目录扫描完成：未发现符合条件的候选目录。")
        return

    log(f"安装目录扫描完成：共发现 {len(results)} 个候选目录。")

    high = [r for r in results if r["risk_level"] == "high"]
    medium = [r for r in results if r["risk_level"] == "medium"]
    low = [r for r in results if r["risk_level"] == "low"]

    log(f"高风险: {len(high)} | 中风险: {len(medium)} | 低风险: {len(low)}")

    for item in results[:15]:
        log(
            f"[扫描候选] {item['name']} | "
            f"大小: {item['size_mb']} MB | "
            f"风险: {item['risk_level']} | "
            f"原因: {item['reason']} | "
            f"路径: {item['path']}"
        )
