# SPDX-License-Identifier: MIT
"""Open a project database without losing a proven Windows path failure."""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import stat


class ProjectStorePathTooLong(sqlite3.OperationalError):
    """The ordinary Windows spelling cannot reach this otherwise accessible store."""


def _extended_windows_path(path: Path) -> str:
    text = str(path.absolute())
    if text.startswith('\\\\?\\'):
        return text
    if text.startswith('\\\\'):
        return '\\\\?\\UNC\\' + text[2:]
    return '\\\\?\\' + text


def _windows_accessible(path: str, *, directory: bool, read_only: bool = False) -> bool:
    """Check access by opening an existing handle; never create or write a file."""
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    # FILE_ADD_FILE for the parent; read or read/write access for an existing DB.
    access = 0x0002 if directory else (0x80000000 if read_only else 0xC0000000)
    flags = 0x02000000 if directory else 0  # FILE_FLAG_BACKUP_SEMANTICS
    handle = create(path, access, 0x00000007, None, 3, flags, None)  # OPEN_EXISTING
    if handle == ctypes.c_void_p(-1).value:
        return False
    close(handle)
    return True


def _windows_path_failure_is_proven(path: Path, *, read_only: bool = False) -> bool:
    """Require an OS difference and access, rather than inferring from length.

    Windows may answer PATH_NOT_FOUND for an overlong ordinary path. Only a
    different result for the *same* extended-length path is useful evidence.
    An inaccessible parent or an existing unwritable/non-file target stays
    undiagnosed; a 503 must not conceal a separate permission problem.
    """
    if os.name != 'nt':
        return False
    try:
        os.stat(path)
    except OSError as ordinary:
        if getattr(ordinary, 'winerror', None) not in (3, 206):
            return False
    else:
        return False

    extended = _extended_windows_path(path)
    try:
        target = os.stat(extended)
    except OSError as error:
        # FILE_NOT_FOUND proves that the extended spelling reached the parent.
        if getattr(error, 'winerror', None) != 2:
            return False
        target = None
    try:
        if read_only:
            return (target is not None and stat.S_ISREG(target.st_mode)
                    and _windows_accessible(extended, directory=False, read_only=True))
        parent = _extended_windows_path(path.parent)
        if not stat.S_ISDIR(os.stat(parent).st_mode) or not _windows_accessible(parent, directory=True):
            return False
        return target is None or (stat.S_ISREG(target.st_mode)
                                  and _windows_accessible(extended, directory=False))
    except OSError:
        return False


def exists(path) -> bool:
    """Do not turn a real but unreachable database into an empty project list."""
    path = Path(path)
    try:
        path.stat()
        return True
    except FileNotFoundError as ordinary:
        if os.name != 'nt' or getattr(ordinary, 'winerror', None) not in (3, 206):
            return False
        extended = _extended_windows_path(path)
        try:
            target = os.stat(extended)
        except FileNotFoundError:
            return False
        if (stat.S_ISREG(target.st_mode)
                and _windows_accessible(extended, directory=False, read_only=True)):
            raise ProjectStorePathTooLong('project store path is inaccessible') from ordinary
        raise sqlite3.OperationalError('project store is inaccessible') from ordinary


def connect(path, *, read_only=False, **kwargs):
    """Retain SQLite errors unless a project-store path failure is demonstrated."""
    path = Path(path)
    try:
        if read_only:
            return sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, **kwargs)
        return sqlite3.connect(str(path), **kwargs)
    except sqlite3.OperationalError as exc:
        code = getattr(exc, 'sqlite_errorcode', None)
        if (code is not None and code & 0xff == sqlite3.SQLITE_CANTOPEN
                and _windows_path_failure_is_proven(path, read_only=read_only)):
            raise ProjectStorePathTooLong('project store path is inaccessible') from exc
        raise
