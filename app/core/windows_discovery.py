from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path, PureWindowsPath
from uuid import UUID

import psutil


def _windows_dll(name: str):
    if os.name != "nt":
        raise OSError("Windows environment discovery requires Windows.")
    return ctypes.WinDLL(name, use_last_error=True)


def known_downloads() -> Path:
    shell = _windows_dll("shell32").SHGetKnownFolderPath
    shell.argtypes = (ctypes.c_void_p, wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p))
    shell.restype = ctypes.c_long
    free = _windows_dll("ole32").CoTaskMemFree
    free.argtypes = (ctypes.c_void_p,)
    free.restype = None

    folder_id = (ctypes.c_uint32 * 4).from_buffer_copy(
        UUID("374de290-123f-4565-9164-39c4925e467b").bytes_le,
    )
    result = ctypes.c_void_p()
    try:
        # KF_FLAG_DONT_VERIFY retrieves the current mapping. The planner checks access.
        hresult = shell(ctypes.byref(folder_id), 0x4000, None, ctypes.byref(result))
        if hresult != 0 or not result.value:
            raise OSError(f"SHGetKnownFolderPath failed (HRESULT 0x{hresult & 0xffffffff:08X}).")
        return Path(ctypes.wstring_at(result))
    finally:
        if result.value:
            free(result)


def _system_drive() -> str:
    get_directory = _windows_dll("kernel32").GetSystemWindowsDirectoryW
    get_directory.argtypes = (wintypes.LPWSTR, wintypes.UINT)
    get_directory.restype = wintypes.UINT
    buffer = ctypes.create_unicode_buffer(32768)
    length = get_directory(buffer, len(buffer))
    drive = PureWindowsPath(buffer.value).drive.upper()
    if not 0 < length < len(buffer) or len(drive) != 2 or not drive.endswith(":"):
        raise OSError("Could not verify the Windows system drive.")
    return drive


def _drive_type(root: str) -> int:
    get_type = _windows_dll("kernel32").GetDriveTypeW
    get_type.argtypes = (wintypes.LPCWSTR,)
    get_type.restype = wintypes.UINT
    return get_type(root)


def _available_bytes(root: str) -> int:
    with os.scandir(root):
        pass
    return psutil.disk_usage(root).free


def fixed_drive_candidates() -> list[tuple[str, int]]:
    """Return readable non-system drive roots in descending free-space order."""
    system_drive = _system_drive()
    candidates: dict[str, int] = {}
    for partition in psutil.disk_partitions(all=False):
        mount = PureWindowsPath(partition.mountpoint)
        drive = mount.drive.upper()
        if len(drive) != 2 or not drive.endswith(":") or drive == system_drive or mount != PureWindowsPath(mount.anchor):
            continue
        root = drive + "\\"
        try:
            if _drive_type(root) == 3:  # DRIVE_FIXED
                free = _available_bytes(root)
                if free > 0:
                    candidates[root] = free
        except (OSError, psutil.Error):
            continue
    return sorted(candidates.items(), key=lambda item: (-item[1], item[0]))
