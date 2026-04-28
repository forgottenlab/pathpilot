from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def calculate_dir_size_mb(path: Path, max_depth: int = 2) -> float:
    total = 0
    base_depth = len(path.parts)

    try:
        for p in path.rglob("*"):
            try:
                if len(p.parts) - base_depth > max_depth:
                    continue
                if p.is_file():
                    total += p.stat().st_size
            except (OSError, PermissionError):
                continue
    except (OSError, PermissionError):
        return 0.0

    return round(total / (1024 * 1024), 2)


def collect_dir_features(path: Path, max_depth: int = 2) -> dict[str, Any]:
    exe_files: list[str] = []
    dll_count = 0
    uninstall_markers: list[str] = []
    driver_like = False
    service_like = False

    base_depth = len(path.parts)

    try:
        for p in path.rglob("*"):
            try:
                if len(p.parts) - base_depth > max_depth:
                    continue

                if p.is_file():
                    suffix = p.suffix.lower()
                    name = p.name.lower()

                    if suffix == ".exe":
                        exe_files.append(p.name)

                    if suffix == ".dll":
                        dll_count += 1

                    if "uninstall" in name or "unins" in name:
                        uninstall_markers.append(p.name)

                    if suffix == ".sys" or "driver" in name:
                        driver_like = True

                    if "service" in name:
                        service_like = True
            except (OSError, PermissionError):
                continue
    except (OSError, PermissionError):
        pass

    return {
        "exe_files": exe_files[:20],
        "exe_count": len(exe_files),
        "dll_count": dll_count,
        "uninstall_markers": uninstall_markers[:10],
        "driver_like": driver_like,
        "service_like": service_like
    }


def assess_risk(
    dir_name: str,
    size_mb: float,
    features: dict[str, Any],
    exclude_keywords: list[str]
) -> tuple[str, str]:
    lowered = dir_name.lower()

    if any(keyword in lowered for keyword in exclude_keywords):
        return "high", "命中高风险关键字"

    if features["driver_like"]:
        return "high", "检测到驱动相关特征"

    if features["service_like"]:
        return "high", "检测到服务相关特征"

    if features["exe_count"] == 0:
        return "low", "未发现可执行主程序，更像普通资源目录"

    if features["exe_count"] > 0 and features["dll_count"] >= 1 and size_mb >= 100:
        return "medium", "疑似完整软件目录，需人工确认"

    if features["exe_count"] > 0 and size_mb < 100:
        return "low", "疑似轻量程序或辅助组件"

    return "medium", "无法明确判断，建议人工确认"


def scan_program_directories(scan_config: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    program_dirs = scan_config.get("program_dirs", [])
    max_depth = int(scan_config.get("max_depth", 2))
    min_size_mb = float(scan_config.get("min_size_mb", 20))
    exclude_dir_names = {name.lower() for name in scan_config.get("exclude_dir_names", [])}
    exclude_keywords = [k.lower() for k in scan_config.get("exclude_keywords", [])]

    for root_str in program_dirs:
        root = Path(root_str)
        if not root.exists():
            continue

        try:
            for child in root.iterdir():
                try:
                    if not child.is_dir():
                        continue

                    if child.name.lower() in exclude_dir_names:
                        continue

                    size_mb = calculate_dir_size_mb(child, max_depth=max_depth)
                    if size_mb < min_size_mb:
                        continue

                    features = collect_dir_features(child, max_depth=max_depth)
                    risk_level, reason = assess_risk(
                        dir_name=child.name,
                        size_mb=size_mb,
                        features=features,
                        exclude_keywords=exclude_keywords
                    )

                    results.append({
                        "name": child.name,
                        "path": str(child),
                        "size_mb": size_mb,
                        "risk_level": risk_level,
                        "reason": reason,
                        "exe_count": features["exe_count"],
                        "dll_count": features["dll_count"],
                        "uninstall_markers": features["uninstall_markers"],
                        "sample_exe_files": features["exe_files"][:5]
                    })
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            continue

    results.sort(key=lambda x: (-x["size_mb"], x["risk_level"]))
    return results


def save_scan_results(results: list[dict[str, Any]], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
