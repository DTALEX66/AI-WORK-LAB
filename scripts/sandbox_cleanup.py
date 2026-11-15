"""Conservative preflight for deleting a disposable, caller-owned sandbox.

The caller is responsible for proving ownership and choosing the target. This
checks the current tree immediately before removal; permissions or contents can
still change afterwards, so a refusal or failed removal must remain visible.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat


def win_long_safe(path):
    """Use extended Windows paths without resolving links in the target tree."""
    text = os.fspath(path)
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return Path(text)
    absolute = os.path.abspath(text)
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


def _win_delete_access(path, metadata):
    """Ask Windows for DELETE, and for attribute writes on read-only entries."""
    try:
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                           ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
        create.restype = wintypes.HANDLE
        close = kernel.CloseHandle
        close.argtypes = (wintypes.HANDLE,)
        close.restype = wintypes.BOOL
        flags = 0x00200000  # FILE_FLAG_OPEN_REPARSE_POINT
        if stat.S_ISDIR(metadata.st_mode):
            flags |= 0x02000000  # FILE_FLAG_BACKUP_SEMANTICS
        rights = 0x10000  # DELETE
        if getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_READONLY", 1):
            rights |= 0x100  # FILE_WRITE_ATTRIBUTES for clearing read-only
        handle = create(str(path), rights, 7, None, 3, flags, None)
        if handle is None or handle == ctypes.c_void_p(-1).value:
            return "DELETE_ACCESS_REFUSED:%s(%s)" % (path, ctypes.get_last_error())
        if not close(handle):
            return "DELETE_CHECK_FAILED:%s(%s)" % (path, ctypes.get_last_error())
    except (OSError, AttributeError, TypeError, ValueError) as error:
        return "DELETE_CHECK_FAILED:%s(%s)" % (path, type(error).__name__)
    return None


def _posix_unlink_allowed(path, metadata):
    """Check parent search/write permission and sticky-directory ownership."""
    try:
        parent = path.parent
        parent_metadata = parent.stat()
        options = {"effective_ids": True} if os.access in os.supports_effective_ids else {}
        if not os.access(parent, os.W_OK | os.X_OK, **options):
            return False
        if parent_metadata.st_mode & stat.S_ISVTX:
            if os.geteuid() not in (0, parent_metadata.st_uid, metadata.st_uid):
                return False
        return True
    except (OSError, AttributeError, NotImplementedError):
        return False


def undeletable_reason(path, *, path_factory=Path, long_safe=win_long_safe):
    """Return the first reason not to delete, or None if the current checks pass.

    Windows DELETE checks are conservative: an entry deletable through its
    parent's DELETE_CHILD alone may be refused. Reparse points are always refused.
    """
    root = long_safe(path)
    refused = []
    sample = None

    def inspect(node):
        try:
            metadata = node.lstat()
        except OSError as error:
            return "METADATA_REFUSED:%s(%s)" % (node, getattr(error, "winerror", None) or error)
        if (stat.S_ISLNK(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)):
            return "REPARSE_POINT_REFUSED:" + str(node)
        if os.name == "nt":
            return _win_delete_access(node, metadata)
        if not _posix_unlink_allowed(node, metadata):
            return "DELETE_ACCESS_REFUSED:" + str(node)
        return None

    reason = inspect(root)
    if reason:
        return reason
    for dirname, dirnames, filenames in os.walk(root, onerror=lambda error: refused.append(error)):
        parent = path_factory(dirname)
        for name in dirnames + filenames:
            reason = inspect(parent / name)
            if reason:
                return reason
        if sample is None and filenames:
            sample = parent / filenames[0]
    if refused:
        return "TRAVERSAL_REFUSED:" + str(getattr(refused[0], "filename", None) or refused[0])
    if sample is not None:
        try:
            sample.read_bytes()
        except OSError as error:
            return "SAMPLE_UNREADABLE:%s(%s)" % (
                sample.name, getattr(error, "winerror", None) or error)
    return None


def clear_read_only(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        raise exc_info[1]
