from __future__ import annotations

import os
import stat
from dataclasses import asdict, dataclass, field
from functools import cache
from os import scandir
from pathlib import Path
from typing import Callable, Literal

import psutil

from app.core.json_store import JsonCorruptError, JsonStoreError, read_json_snapshot
from app.core.path_policy import (
    PathPolicyError,
    normalize_path,
    validate_root_directory,
    validate_source_directory,
)
from app.core.paths import DEFAULT_SETTINGS, get_settings_path
from app.core.settings import build_runtime_paths, runtime_directories
from app.core.windows_discovery import fixed_drive_candidates, known_downloads


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
    root_origin: str | None = None
    root_reason: str | None = None
    source_origin: str | None = None
    source_reason: str | None = None

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
        plan.blockers.append(PlanningBlocker(
            str(source), "source_missing", "Source directory does not exist. Pass --source with an existing directory.",
        ))
    except OSError as exc:
        plan.blockers.append(PlanningBlocker(
            str(source), "source_unavailable", f"{exc} Pass --source with an existing, readable directory.",
        ))


@dataclass(frozen=True)
class _PathChoice:
    path: str
    origin: str
    reason: str


def _root_choices(root: str | None, settings: dict) -> list[_PathChoice]:
    if root is not None:
        return [_PathChoice(root, "cli", "Explicit --root.")]
    base_paths = settings.get("base_paths", {})
    if not isinstance(base_paths, dict) or not isinstance(base_paths.get("root_dir", ""), str):
        raise ValueError("settings.json base_paths.root_dir must be a path string.")
    saved = base_paths.get("root_dir", "")
    if saved.strip():
        return [_PathChoice(saved, "config", "Saved base_paths.root_dir.")]
    if os.environ.get("PATHPILOT_HOME"):
        isolated = build_runtime_paths({})["root_dir"]
        return [_PathChoice(isolated, "isolated", "Managed root under the isolated PATHPILOT_HOME runtime.")]

    choices = [
        _PathChoice(str(Path(drive) / "PathPilot"), "fixed_drive",
                    f"Eligible non-system fixed drive {drive} with {free} free bytes.")
        for drive, free in fixed_drive_candidates()
    ]
    choices.append(_PathChoice(str(Path.home() / "PathPilot"), "profile",
                               "User profile fallback when no safe non-system fixed-drive layout is available."))
    return choices


def _source_choice(
    source: str | None, settings: dict, runtime: dict, saved_incoming: Path | None,
    downloads: Callable[[], _PathChoice],
) -> _PathChoice:
    if source is not None:
        return _PathChoice(source, "cli", "Explicit --source.")
    entries = settings.get("watch_directories", [])
    if not isinstance(entries, list) or any(not isinstance(item, str) for item in entries):
        raise ValueError("settings.json watch_directories must be a list of path strings.")

    internal_paths = {_absolute_path(runtime["incoming_root"]), saved_incoming}
    external = [
        item for item in entries
        if item.strip() == "{user_downloads}"
        or _absolute_path(item.format(**runtime)) not in internal_paths
    ]
    if len(external) > 1:
        raise ValueError(f"Found {len(external)} external sources. Setup plan supports one source per preview.")
    if not external or external[0].strip() == "{user_downloads}":
        return downloads()
    value = external[0]
    if "{user_downloads}" in value:
        runtime = {**runtime, "user_downloads": downloads().path}
    return _PathChoice(value.format(**runtime), "config", "Saved external watch_directories entry.")


def _plan_for_root(
    choice: _PathChoice, source: str | None, settings: dict, saved_incoming: Path | None,
    downloads: Callable[[], _PathChoice],
) -> SetupPlan:
    plan = SetupPlan(choice.path, source or "", root_origin=choice.origin, root_reason=choice.reason)
    if source is not None:
        plan.source_origin, plan.source_reason = "cli", "Explicit --source."
    root = choice.path
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
        selected = _source_choice(source, settings, runtime_paths, saved_incoming, downloads)
        plan.source = selected.path
        plan.source_origin, plan.source_reason = selected.origin, selected.reason
    except (AttributeError, KeyError, IndexError, ValueError, TypeError) as exc:
        plan.blockers.append(PlanningBlocker(plan.source, "source_config", f"{exc} Check watch_directories or pass --source."))
        return plan
    except (OSError, RuntimeError) as exc:
        plan.blockers.append(PlanningBlocker(plan.source, "downloads_discovery", f"{exc} Pass --source with an existing, readable directory."))
        return plan

    try:
        source_path = normalize_path(plan.source)
        plan.source = str(source_path)
        _evaluate_source(source_path, runtime_paths, plan)
    except (OSError, RuntimeError, ValueError) as exc:
        plan.blockers.append(PlanningBlocker(plan.source, "source_unavailable", str(exc)))
    return plan


def plan_setup(root: str | None = None, source: str | None = None) -> SetupPlan:
    """Preview the selected layout using a read-only settings snapshot."""
    plan = SetupPlan(root or "", source or "")
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
        choices = _root_choices(root, settings)
    except (OSError, RuntimeError, ValueError, psutil.Error) as exc:
        plan.blockers.append(PlanningBlocker(plan.root, "root_discovery", f"{exc} Pass --root to select a directory."))
        return plan

    saved_incoming = None
    if source is None:
        base_paths = settings.get("base_paths")
        saved = base_paths.get("root_dir") if isinstance(base_paths, dict) else None
        if isinstance(saved, str) and saved.strip():
            try:
                runtime = build_runtime_paths({"base_paths": {"root_dir": str(_absolute_path(saved))}})
                saved_incoming = _absolute_path(runtime["incoming_root"])
            except (OSError, RuntimeError, ValueError):
                # An invalid root is reported when its plan is evaluated.
                pass

    @cache
    def downloads() -> _PathChoice:
        if os.environ.get("PATHPILOT_HOME"):
            isolated = build_runtime_paths({})["user_downloads"]
            return _PathChoice(isolated, "isolated", "Downloads under the isolated PATHPILOT_HOME runtime.")
        return _PathChoice(str(known_downloads()), "known_folder", "Windows Downloads Known Folder.")

    first_plan = None
    candidate_blockers = {
        "root_policy", "path_escape", "managed_redirect", "target_unavailable", "file_conflict", "source_policy",
    }
    for choice in choices:
        candidate_plan = _plan_for_root(choice, source, settings, saved_incoming, downloads)
        if candidate_plan.status == "ready":
            return candidate_plan
        if first_plan is None:
            first_plan = candidate_plan
        if not any(blocker.code in candidate_blockers for blocker in candidate_plan.blockers):
            return candidate_plan
    return first_plan if first_plan is not None else plan
