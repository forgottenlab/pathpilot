from __future__ import annotations

import shutil
from pathlib import Path


def resolve_conflict(target_file: Path) -> Path:
    if not target_file.exists():
        return target_file

    stem = target_file.stem
    suffix = target_file.suffix
    parent = target_file.parent

    index = 1
    while True:
        candidate = parent / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def move_file(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_file = dst_dir / src.name
    final_target = resolve_conflict(dst_file)
    shutil.move(str(src), str(final_target))
    return final_target
