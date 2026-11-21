from __future__ import annotations

import os
import stat
from dataclasses import asdict, dataclass, field
from os import scandir
from pathlib import Path
from typing import Literal

from app.core.json_store import JsonCorruptError, JsonStoreError, read_json_snapshot
from app.core.path_policy import (
    PathPolicyError,
    normalize_path,
    validate_root_directory,
    validate_source_directory,
)
from app.core.paths import DEFAULT_SETTINGS, get_settings_path
from app.core.settings import build_runtime_paths, runtime_directories


@dataclass(frozen=True)
class PlanningBlocker:
    path: str
    code: str
    reason: str


@dataclass(frozen=True)
class DirectoryAction:
    path: str
    action: Literal["create", "reuse", "blocked"]
    verify_at_apply: bool


@dataclass
class SetupPlan:
    root: str
    source: str
    directories: list[DirectoryAction] = field(default_factory=list)
    blockers: list[PlanningBlocker] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "blocked" if self.blockers else "ready"

    def to_dict(self) -> dict:
        return {"schema_version": 1, "status": self.status, **asdict(self)}


def _absolute_path(value: str) -> Path:
    expanded = os.path.expandvars(value.strip())
    if not expanded:
        raise ValueError("A path cannot be empty.")
    return Path(os.path.abspath(Path(expanded).expanduser()))


def _inspect_directory(path: Path) -> Literal["create", "reuse"]:
    # A missing leaf can hide a file in one of its ancestor positions.
    for candidate in (path, *path.parents):
        try:
            mode = candidate.stat().st_mode
        except FileNotFoundError:
            # A dangling link cannot be created as an ordinary directory.
            if candidate.is_symlink() or candidate.is_junction():
                raise NotADirectoryError(f"Directory link is unavailable: {candidate}")
            continue
        if not stat.S_ISDIR(mode):
            raise NotADirectoryError(f"Path is occupied by a non-directory: {candidate}")
        return "reuse" if candidate == path else "create"
    raise OSError("No existing parent directory was found.")


def _evaluate_target(path: Path, root: Path, plan: SetupPlan) -> None:
    try:
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            plan.blockers.append(PlanningBlocker(
                str(path), "path_escape", f"Target resolves outside the planned root: {resolved}",
            ))
        elif resolved != path:
            plan.blockers.append(PlanningBlocker(
                str(path), "managed_redirect", f"Target redirects to another path: {resolved}",
            ))
        else:
            action = _inspect_directory(path)
            plan.directories.append(DirectoryAction(str(path), action, verify_at_apply=True))
            return
    except NotADirectoryError as exc:
        plan.blockers.append(PlanningBlocker(str(path), "file_conflict", str(exc)))
    except (OSError, RuntimeError, ValueError) as exc:
        plan.blockers.append(PlanningBlocker(str(path), "target_unavailable", str(exc)))
    plan.directories.append(DirectoryAction(str(path), "blocked", verify_at_apply=False))


def _evaluate_source(source: Path, runtime_paths: dict, plan: SetupPlan) -> None:
    try:
        validate_source_directory(source, runtime_paths)
    except PathPolicyError as exc:
        plan.blockers.append(PlanningBlocker(str(source), "source_policy", exc.en))
        return

    try:
        if not stat.S_ISDIR(source.stat().st_mode):
            raise NotADirectoryError("The source must be an existing directory.")
        # Open the directory to test list access without scanning its contents.
        with scandir(source):
            pass
    except FileNotFoundError:
        plan.blockers.append(PlanningBlocker(str(source), "source_missing", "Source directory does not exist."))
    except OSError as exc:
        plan.blockers.append(PlanningBlocker(str(source), "source_unavailable", str(exc)))


def plan_setup(root: str, source: str) -> SetupPlan:
    """Preview explicit paths using a snapshot and read-only filesystem checks."""
    plan = SetupPlan(root, source)
    try:
        settings_path = get_settings_path()
        settings = read_json_snapshot(settings_path, default=DEFAULT_SETTINGS, expected_type=dict)
    except JsonCorruptError as exc:
        plan.blockers.append(PlanningBlocker(str(exc.path), "settings_corrupt", str(exc)))
        return plan
    except (JsonStoreError, OSError, RuntimeError, ValueError) as exc:
        plan.blockers.append(PlanningBlocker("settings.json", "settings_unavailable", str(exc)))
        return plan

    try:
        root_path = _absolute_path(root)
        plan.root = str(root_path)
        resolved_root = validate_root_directory(root)
    except (OSError, RuntimeError, ValueError) as exc:
        plan.blockers.append(PlanningBlocker(plan.root, "root_policy", str(exc)))
        return plan
    if resolved_root != root_path:
        plan.blockers.append(PlanningBlocker(
            plan.root, "path_escape", f"Root redirects to another path: {resolved_root}",
        ))
        plan.directories.append(DirectoryAction(plan.root, "blocked", verify_at_apply=False))
        return plan

    runtime_paths = build_runtime_paths({**settings, "base_paths": {"root_dir": plan.root}})
    for target in runtime_directories(runtime_paths):
        _evaluate_target(Path(target), root_path, plan)

    try:
        source_path = normalize_path(source)
        plan.source = str(source_path)
        _evaluate_source(source_path, runtime_paths, plan)
    except (OSError, RuntimeError, ValueError) as exc:
        plan.blockers.append(PlanningBlocker(plan.source, "source_unavailable", str(exc)))
    return plan
