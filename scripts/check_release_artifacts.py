from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path


FORBIDDEN_PARTS = {
    ".ai",
    "tests",
    "data",
    "logs",
    "backups",
    ".pathpilot",
    "config",
}
REQUIRED_WHEEL_PREFIXES = {
    "app/core/",
    "app/files/",
    "app/installers/",
    "app/gui/",
}
REQUIRED_WHEEL_FILES = {"README.md", "README.zh-CN.md"}
REQUIRED_SDIST_FILES = {
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "README.zh-CN.md",
    "SECURITY.md",
}


def archive_names(path: Path) -> list[str]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return archive.namelist()
    with tarfile.open(path, "r:gz") as archive:
        return archive.getnames()


def check_archive(path: Path) -> None:
    names = archive_names(path)
    for name in names:
        parts = set(Path(name).parts)
        forbidden = parts.intersection(FORBIDDEN_PARTS)
        wheel_doc = (
            path.suffix == ".whl"
            and Path(name).name in REQUIRED_WHEEL_FILES
            and "/data/share/doc/pathpilot/" in name.replace("\\", "/")
        )
        if wheel_doc:
            forbidden.discard("data")
        if forbidden:
            raise RuntimeError(f"{path.name} contains forbidden path {name}: {sorted(forbidden)}")
        lowered = name.lower()
        if lowered.endswith((".log", ".corrupt")) or "pending_installs.json" in lowered:
            raise RuntimeError(f"{path.name} contains runtime state: {name}")

    if path.suffix == ".whl":
        for prefix in REQUIRED_WHEEL_PREFIXES:
            if not any(name.startswith(prefix) for name in names):
                raise RuntimeError(f"{path.name} is missing package prefix: {prefix}")
        basenames = {Path(name).name for name in names}
        missing = REQUIRED_WHEEL_FILES.difference(basenames)
        if missing:
            raise RuntimeError(f"{path.name} is missing release documents: {sorted(missing)}")
    else:
        basenames = {Path(name).name for name in names}
        missing = REQUIRED_SDIST_FILES.difference(basenames)
        if missing:
            raise RuntimeError(f"{path.name} is missing release documents: {sorted(missing)}")


def main() -> None:
    dist = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit(f"Expected one wheel and one sdist in {dist}; got {wheels} and {sdists}")
    for artifact in [*wheels, *sdists]:
        check_archive(artifact)
        print(f"PASS {artifact.name}: {len(archive_names(artifact))} entries")


if __name__ == "__main__":
    main()
