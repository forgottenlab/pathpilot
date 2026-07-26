from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TypeVar


T = TypeVar("T")
_MISSING = object()
_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


class JsonStoreError(RuntimeError):
    pass


class JsonLockTimeout(JsonStoreError):
    def __init__(self, path: Path, timeout: float) -> None:
        self.path = path
        self.timeout = timeout
        super().__init__(f"Timed out after {timeout:.2f}s waiting for JSON lock: {path}")


class JsonCorruptError(JsonStoreError):
    def __init__(self, path: Path, backup_path: Path | None, detail: str) -> None:
        self.path = path
        self.backup_path = backup_path
        self.detail = detail
        backup = f" Corrupt data preserved at: {backup_path}." if backup_path else ""
        super().__init__(f"Invalid JSON state: {path}. {detail}.{backup}")


@dataclass(frozen=True)
class JsonFileStatus:
    path: Path
    exists: bool
    valid: bool
    error: str | None = None
    corrupt_backups: tuple[Path, ...] = ()


def _thread_lock(path: Path) -> threading.RLock:
    key = os.path.normcase(str(path.resolve(strict=False)))
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


class InterProcessFileLock:
    def __init__(self, target_path: str | Path, timeout: float = 5.0, poll: float = 0.05) -> None:
        self.target_path = Path(target_path)
        self.lock_path = self.target_path.with_name(f"{self.target_path.name}.lock")
        self.timeout = timeout
        self.poll = poll
        self._thread_lock = _thread_lock(self.lock_path)
        self._handle = None

    def __enter__(self) -> InterProcessFileLock:
        deadline = time.monotonic() + self.timeout
        remaining = max(0.0, deadline - time.monotonic())
        if not self._thread_lock.acquire(timeout=remaining):
            raise JsonLockTimeout(self.target_path, self.timeout)

        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = self.lock_path.open("a+b")
            self._handle.seek(0, os.SEEK_END)
            if self._handle.tell() == 0:
                self._handle.write(b"\0")
                self._handle.flush()

            while True:
                try:
                    self._lock_once()
                    return self
                except (BlockingIOError, OSError):
                    if time.monotonic() >= deadline:
                        raise JsonLockTimeout(self.target_path, self.timeout)
                    time.sleep(min(self.poll, max(0.0, deadline - time.monotonic())))
        except Exception as exc:
            if self._handle is not None:
                self._handle.close()
                self._handle = None
            self._thread_lock.release()
            if isinstance(exc, (JsonStoreError, TypeError, ValueError)):
                raise
            if isinstance(exc, OSError):
                raise JsonStoreError(
                    f"Failed to acquire JSON lock for {self.target_path}: {exc}"
                ) from exc
            raise

    def _lock_once(self) -> None:
        assert self._handle is not None
        self._handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def __exit__(self, exc_type, exc, traceback) -> None:
        try:
            if self._handle is not None:
                try:
                    self._handle.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
                finally:
                    self._handle.close()
                    self._handle = None
        finally:
            self._thread_lock.release()


def _corrupt_backups(path: Path) -> tuple[Path, ...]:
    return tuple(sorted(path.parent.glob(f"{path.name}.*.corrupt"))) if path.parent.exists() else ()


def _isolate_corrupt_unlocked(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = path.with_name(f"{path.name}.{stamp}.corrupt")
    try:
        os.replace(path, backup)
    except OSError as exc:
        raise JsonStoreError(
            f"Failed to preserve corrupt JSON state {path}: {exc}"
        ) from exc
    return backup


def _load_unlocked(
    path: Path,
    *,
    default: Any = _MISSING,
    expected_type: type | tuple[type, ...] | None = None,
    isolate_corrupt: bool = True,
) -> Any:
    if not path.exists():
        backups = _corrupt_backups(path)
        if backups:
            raise JsonCorruptError(
                path,
                backups[-1],
                "A corrupt backup exists; explicit reset is required",
            )
        if default is _MISSING:
            raise FileNotFoundError(path)
        return deepcopy(default)

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        backup = _isolate_corrupt_unlocked(path) if isolate_corrupt else None
        raise JsonCorruptError(path, backup, str(exc)) from exc
    except OSError as exc:
        raise JsonStoreError(f"Failed to read JSON state {path}: {exc}") from exc

    if expected_type is not None and not isinstance(data, expected_type):
        detail = f"Expected {expected_type}, got {type(data).__name__}"
        backup = _isolate_corrupt_unlocked(path) if isolate_corrupt else None
        raise JsonCorruptError(path, backup, detail)
    return data


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    directory_fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _atomic_write_unlocked(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        _fsync_directory(path.parent)
    except Exception as exc:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        if isinstance(exc, OSError):
            raise JsonStoreError(f"Failed to atomically write JSON state {path}: {exc}") from exc
        raise


def atomic_write_json(
    path: str | Path,
    data: Any,
    *,
    lock_timeout: float = 5.0,
) -> None:
    target = Path(path)
    with InterProcessFileLock(target, timeout=lock_timeout):
        _atomic_write_unlocked(target, data)


def read_json(
    path: str | Path,
    *,
    default: Any = _MISSING,
    expected_type: type | tuple[type, ...] | None = None,
    lock_timeout: float = 5.0,
) -> Any:
    target = Path(path)
    with InterProcessFileLock(target, timeout=lock_timeout):
        return _load_unlocked(target, default=default, expected_type=expected_type)


def read_json_snapshot(
    path: str | Path,
    *,
    default: Any = _MISSING,
    expected_type: type | tuple[type, ...] | None = None,
) -> Any:
    """Read an atomic JSON snapshot without creating a lock or modifying corruption."""
    return _load_unlocked(
        Path(path),
        default=default,
        expected_type=expected_type,
        isolate_corrupt=False,
    )


def update_json(
    path: str | Path,
    updater: Callable[[Any], T],
    *,
    default: Any,
    expected_type: type | tuple[type, ...] | None = None,
    lock_timeout: float = 5.0,
) -> T:
    target = Path(path)
    with InterProcessFileLock(target, timeout=lock_timeout):
        current = _load_unlocked(target, default=default, expected_type=expected_type)
        result = updater(current)
        _atomic_write_unlocked(target, current)
        return result


def ensure_json_file(
    path: str | Path,
    default: Any,
    *,
    expected_type: type | tuple[type, ...] | None = None,
    lock_timeout: float = 5.0,
) -> None:
    target = Path(path)
    with InterProcessFileLock(target, timeout=lock_timeout):
        if target.exists() or _corrupt_backups(target):
            _load_unlocked(target, expected_type=expected_type)
            return
        _atomic_write_unlocked(target, deepcopy(default))


def reset_json(path: str | Path, default: Any, *, lock_timeout: float = 5.0) -> None:
    atomic_write_json(path, deepcopy(default), lock_timeout=lock_timeout)


def inspect_json(
    path: str | Path,
    *,
    expected_type: type | tuple[type, ...] | None = None,
) -> JsonFileStatus:
    target = Path(path)
    backups = _corrupt_backups(target)
    if not target.exists():
        error = "missing"
        if backups:
            error = f"missing; corrupt backup retained at {backups[-1]}"
        return JsonFileStatus(target, False, False, error, backups)
    try:
        _load_unlocked(target, expected_type=expected_type, isolate_corrupt=False)
    except (JsonStoreError, OSError) as exc:
        return JsonFileStatus(target, True, False, str(exc), backups)
    return JsonFileStatus(target, True, True, None, backups)
