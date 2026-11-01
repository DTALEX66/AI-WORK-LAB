#!/usr/bin/env python
"""Install the Codex baseline into an existing real Codex Home without overwrites."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import errno
import os
from pathlib import Path
import secrets
from typing import Iterator


ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "packages/client-neutral-core/templates/agent-rules/CODEX_GLOBAL_AGENTS.md"


class CleanupIncompleteError(RuntimeError):
    """The installer could not prove that its newly created target was removed."""


class DirectoryFinalizeError(OSError):
    """The pinned Codex Home handle could not be closed cleanly."""


class StagingCreateError(OSError):
    """A private staging object could not be converted into a Python descriptor."""


class AtomicPublishUnsupportedError(OSError):
    """The platform cannot publish a complete staging object without replacement."""


def is_link_or_reparse_point(path: Path) -> bool:
    """Reject links so this installer cannot redirect writes outside Codex Home."""
    try:
        status = path.lstat()
    except FileNotFoundError:
        return False
    reparse_flag = getattr(os, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    return path.is_symlink() or bool(getattr(status, "st_file_attributes", 0) & reparse_flag)


def linked_ancestor(path: Path) -> Path | None:
    """Return the first link/reparse point from a target up to its volume root."""
    current = path.absolute()
    while True:
        if is_link_or_reparse_point(current):
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


@contextmanager
def pinned_directory(path: Path) -> Iterator[int]:
    """Pin a real directory while the target is created inside it.

    A Windows GENERIC_READ directory handle opened without FILE_SHARE_DELETE
    prevents the directory from being renamed into a junction after the final
    reparse check. POSIX callers receive an O_NOFOLLOW dirfd for relative
    target operations.
    """
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        create_file = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        close_handle = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL

        generic_read = 0x80000000
        share_read_write = 0x00000001 | 0x00000002
        open_existing = 3
        backup_semantics = 0x02000000
        open_reparse_point = 0x00200000
        handle = create_file(
            str(path),
            generic_read,
            share_read_write,
            None,
            open_existing,
            backup_semantics | open_reparse_point,
            None,
        )
        invalid_handle = ctypes.c_void_p(-1).value
        if handle in (None, invalid_handle):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            yield int(handle)
        finally:
            if not close_handle(handle):
                error = ctypes.WinError(ctypes.get_last_error())
                raise DirectoryFinalizeError(str(error)) from error
        return

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        if not os.path.samestat(os.fstat(descriptor), path.lstat()):
            raise OSError("Codex Home changed while its directory handle was opened")
        yield descriptor
    finally:
        try:
            os.close(descriptor)
        except OSError as error:
            raise DirectoryFinalizeError(str(error)) from error


def entry_exists(parent: Path, name: str, directory_fd: int | None) -> bool:
    """Check an entry without following links, relative to a pinned dirfd when available."""
    try:
        if os.name == "nt" or directory_fd is None:
            (parent / name).lstat()
        else:
            os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def _windows_close_raw_handle(handle: int) -> None:
    import ctypes
    from ctypes import wintypes

    close_handle = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    if not close_handle(handle):
        raise ctypes.WinError(ctypes.get_last_error())


# Windows staging used to be marked delete-pending through SetFileInformationByHandle so that nobody
# could open it between creation and publication. Measured 2026-10-12 on this host: that call returned
# WinError 24, the failure was printed and then swallowed, and the installer went on to report
# CODEX_GUIDANCE_WRITTEN with exit 0 while AGENTS.md did not exist. The disposition was also one-way
# (legacy FileDispositionInfo cannot be withdrawn), which the publish path depended on.
#
# It is removed rather than worked around, and the property it provided is kept by something stronger:
# the staging handle is opened with FILE_SHARE_NONE, so while content is written NO other handle can be
# opened to that entry -- it cannot be hard-linked, read or replaced, which is the guarantee
# test_codex_global_guidance_does_not_write_through_a_post_create_hardlink measures. Publication still
# goes through our own handle (SetFileInformationByHandle never needs the name), so an abandoned
# attempt is simply closed and removed by name in discard_private_staging.
def _windows_discard_descriptor(descriptor: int) -> None:
    """Close the staging descriptor; the caller removes the entry by name."""
    import msvcrt

    handle = msvcrt.get_osfhandle(descriptor)
    try:
        os.close(descriptor)
    except OSError as error:
        try:
            _windows_close_raw_handle(handle)
        except OSError as close_error:
            raise CleanupIncompleteError from close_error
        raise CleanupIncompleteError from error
def create_private_staging(codex_home: Path, directory_fd: int) -> tuple[int, str | None]:
    """Create a private staging object; ``None`` means an unnamed POSIX inode."""
    staging_name = f".workflow-assistance-AGENTS-{secrets.token_hex(16)}.tmp"
    if os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        staging_path = codex_home / staging_name
        handle = create_file(
            str(staging_path),
            0x40000000 | 0x00010000,  # GENERIC_WRITE | DELETE
            0,  # FILE_SHARE_NONE: while content is written, no other handle can be opened
            #            to the staging entry, so it cannot be hard-linked or read either.
            None,
            1,  # CREATE_NEW
            0x00000080 | 0x00200000,  # NORMAL | OPEN_REPARSE_POINT
            None,
        )
        invalid_handle = ctypes.c_void_p(-1).value
        if handle in (None, invalid_handle):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            descriptor = msvcrt.open_osfhandle(
                handle,
                os.O_WRONLY | getattr(os, "O_BINARY", 0),
            )
        except BaseException as error:
            # Windows staging is a named file with no delete-pending disposition, so a failure
            # after CREATE_NEW has to remove that name itself. Leaving it behind is exactly what
            # test_codex_global_guidance_cleans_staging_if_open_osfhandle_fails measures.
            try:
                _windows_close_raw_handle(handle)
            except OSError as cleanup_error:
                raise CleanupIncompleteError from cleanup_error
            try:
                staging_path.unlink()
            except FileNotFoundError:
                pass
            except OSError as cleanup_error:
                raise CleanupIncompleteError from cleanup_error
            raise StagingCreateError(str(error)) from error
        return descriptor, staging_name

    anonymous_flag = getattr(os, "O_TMPFILE", 0)
    if not anonymous_flag:
        raise AtomicPublishUnsupportedError("O_TMPFILE is unavailable")
    try:
        descriptor = os.open(
            ".",
            os.O_RDWR | anonymous_flag,
            0o600,
            dir_fd=directory_fd,
        )
    except OSError as error:
        if error.errno in {errno.EINVAL, errno.EOPNOTSUPP, errno.ENOTSUP}:
            raise AtomicPublishUnsupportedError("O_TMPFILE is unavailable") from error
        raise
    return descriptor, None


def discard_private_staging(descriptor: int, staging_name: str | None, 
                     codex_home: Path | None = None) -> bool:
    """Close staging safely; return whether an unremovable staging file remains."""
    try:
        if os.name == "nt":
            _windows_discard_descriptor(descriptor)
            descriptor = -1
        else:
            os.close(descriptor)
            descriptor = -1
        # Windows staging is an ordinary file now (no delete-pending disposition),
        # so an abandoned attempt has to be removed by name. POSIX staging is an
        # unnamed inode and disappears with the last close, which is why this is
        # Windows-only work.
        if os.name == "nt" and staging_name and codex_home is not None:
            try:
                (codex_home / staging_name).unlink()
            except FileNotFoundError:
                pass
            except OSError as error:
                raise CleanupIncompleteError from error
        return False
    except OSError as error:
        raise CleanupIncompleteError from error


def publish_private_staging(
    target: Path,
    descriptor: int,
    directory_fd: int,
    staging_name: str | None,
) -> None:
    """Atomically expose complete content at AGENTS.md without replacement."""
    if os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes

        destination = str(target)

        class FileRenameInfo(ctypes.Structure):
            _fields_ = [
                ("ReplaceIfExists", wintypes.BOOL),
                ("RootDirectory", wintypes.HANDLE),
                ("FileNameLength", wintypes.DWORD),
                ("FileName", wintypes.WCHAR * (len(destination) + 1)),
            ]

        information = FileRenameInfo()
        information.ReplaceIfExists = False
        information.RootDirectory = None
        information.FileNameLength = len(destination.encode("utf-16-le"))
        information.FileName = destination
        set_file_information = ctypes.WinDLL(
            "kernel32",
            use_last_error=True,
        ).SetFileInformationByHandle
        set_file_information.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        set_file_information.restype = wintypes.BOOL
        if not set_file_information(
            msvcrt.get_osfhandle(descriptor),
            3,  # FileRenameInfo
            ctypes.byref(information),
            ctypes.sizeof(information),
        ):
            error_code = ctypes.get_last_error()
            if error_code in {80, 183}:
                raise FileExistsError(errno.EEXIST, "Codex guidance target exists", str(target))
            raise ctypes.WinError(error_code)
        return

    import ctypes

    libc = ctypes.CDLL(None, use_errno=True)
    linkat = getattr(libc, "linkat", None)
    if linkat is None:
        raise AtomicPublishUnsupportedError("linkat is unavailable")
    linkat.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    linkat.restype = ctypes.c_int
    if linkat(descriptor, b"", directory_fd, os.fsencode(target.name), 0x1000) != 0:
        error_code = ctypes.get_errno()
        if error_code == errno.EEXIST:
            raise FileExistsError(errno.EEXIST, "Codex guidance target exists", str(target))
        raise OSError(error_code, os.strerror(error_code), str(target))


def home_identity_matches(codex_home: Path, directory_fd: int) -> bool:
    if os.name == "nt":
        return linked_ancestor(codex_home) is None and codex_home.is_dir()
    try:
        return os.path.samestat(os.fstat(directory_fd), codex_home.lstat())
    except FileNotFoundError:
        return False


def public_target_matches(target: Path, descriptor: int, directory_fd: int) -> bool:
    try:
        if os.name == "nt":
            current = target.lstat()
        else:
            current = os.stat(target.name, dir_fd=directory_fd, follow_symlinks=False)
        return os.path.samestat(os.fstat(descriptor), current)
    except FileNotFoundError:
        return False


def write_all(descriptor: int, content: bytes) -> None:
    """Write every byte while preserving the open handle for failure cleanup."""
    offset = 0
    while offset < len(content):
        written = os.write(descriptor, content[offset:])
        if written <= 0:
            raise OSError(f"short Codex guidance write: {offset}/{len(content)} bytes")
        offset += written


def plan(codex_home: Path) -> tuple[int, str, Path]:
    """Return a non-destructive action code, marker, and target path."""
    target = codex_home / "AGENTS.md"
    override = codex_home / "AGENTS.override.md"
    if not codex_home.exists():
        return 5, "CODEX_GUIDANCE_HOME_MISSING", target
    if not codex_home.is_dir():
        return 6, "CODEX_GUIDANCE_HOME_INVALID", target
    if override.exists():
        return 2, "CODEX_GUIDANCE_BLOCKED_OVERRIDE", target
    if target.exists():
        if target.is_file() and target.stat().st_size == 0:
            if target.stat().st_nlink != 1:
                return 4, "CODEX_GUIDANCE_BLOCKED_HARDLINK", target
            return 3, "CODEX_GUIDANCE_BLOCKED_EMPTY", target
        return 1, "CODEX_GUIDANCE_EXISTS", target
    return 0, "CODEX_GUIDANCE_READY", target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install the Workflow-assistance Codex global baseline only when Codex Home already exists "
            "and no user rule file exists."
        )
    )
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "require an existing Codex Home and exclusively create AGENTS.md only when it is absent; "
            "existing empty files are preserved"
        ),
    )
    args = parser.parse_args(argv)

    codex_home = args.codex_home.expanduser().absolute()
    unsafe_ancestor = linked_ancestor(codex_home)
    if unsafe_ancestor is not None:
        print(f"CODEX_GUIDANCE_BLOCKED_LINK target={codex_home} ancestor={unsafe_ancestor}")
        print("No existing Codex rule file was changed.")
        return 0
    code, marker, target = plan(codex_home)
    print(f"{marker} target={target}")
    if code in {1, 2, 3, 4}:
        print("No existing Codex rule file was changed.")
        return 0
    if code in {5, 6}:
        print("Initialize Codex Home with the official Codex application before installing guidance.")
        return 1 if args.apply else 0
    if not args.apply:
        print("Run again with --apply to create the global baseline.")
        return 0

    try:
        content = TEMPLATE.read_bytes()
    except OSError as error:
        print(f"CODEX_GUIDANCE_TEMPLATE_READ_FAILED target={target} reason={type(error).__name__}")
        return 1

    staging_created = False
    public_target_created = False
    try:
        with pinned_directory(codex_home) as directory_fd:
            unsafe_ancestor = linked_ancestor(target)
            if unsafe_ancestor is not None:
                print(f"CODEX_GUIDANCE_BLOCKED_LINK target={target} ancestor={unsafe_ancestor}")
                print("No existing Codex rule file was changed.")
                return 0
            # Re-check the higher-priority override while Codex Home is pinned.
            if entry_exists(codex_home, "AGENTS.override.md", directory_fd):
                print(f"CODEX_GUIDANCE_BLOCKED_OVERRIDE target={target}")
                print("No existing Codex rule file was changed.")
                return 0
            # A user rule file may have appeared after the initial preview.
            # Re-plan before allocating staging so an existing user target is
            # preserved even on filesystems without anonymous staging support.
            current_code, current_marker, _ = plan(codex_home)
            if current_code in {1, 2, 3, 4}:
                print(f"{current_marker} target={target}")
                print("No existing Codex rule file was changed.")
                return 0
            try:
                descriptor, staging_name = create_private_staging(codex_home, directory_fd)
            except StagingCreateError as error:
                print(
                    f"CODEX_GUIDANCE_STAGING_CREATE_FAILED_CLEANED target={target} "
                    f"reason={type(error.__cause__).__name__}"
                )
                return 1
            except AtomicPublishUnsupportedError:
                print(f"CODEX_GUIDANCE_ATOMIC_PUBLISH_UNSUPPORTED target={target}")
                print("No public AGENTS.md or private staging object was created.")
                return 1
            staging_created = True

            try:
                write_all(descriptor, content)
            except OSError as error:
                retained = discard_private_staging(descriptor, staging_name, codex_home)
                marker = (
                    "CODEX_GUIDANCE_WRITE_INCOMPLETE"
                    if retained
                    else "CODEX_GUIDANCE_WRITE_FAILED_CLEANED"
                )
                print(f"{marker} target={target} reason={type(error).__name__}")
                print("No public AGENTS.md was created; inspect any reported private staging file.")
                return 1

            if not home_identity_matches(codex_home, directory_fd):
                retained = discard_private_staging(descriptor, staging_name, codex_home)
                print(f"CODEX_GUIDANCE_HOME_CHANGED target={target} staging_retained={retained}")
                print("No public AGENTS.md was created.")
                return 1

            if entry_exists(codex_home, "AGENTS.override.md", directory_fd):
                retained = discard_private_staging(descriptor, staging_name, codex_home)
                print(
                    f"CODEX_GUIDANCE_OVERRIDE_BEFORE_PUBLICATION target={target} "
                    f"staging_retained={retained}"
                )
                print("No public AGENTS.md was created.")
                return 1

            if not home_identity_matches(codex_home, directory_fd):
                retained = discard_private_staging(descriptor, staging_name, codex_home)
                print(f"CODEX_GUIDANCE_HOME_CHANGED target={target} staging_retained={retained}")
                print("No public AGENTS.md was created.")
                return 1

            # The staging entry must have no link but its own. POSIX uses an anonymous
            # O_TMPFILE inode, which reports zero links. Windows staging is a NAMED file now
            # (the delete-pending disposition it used to carry is gone -- see the note above),
            # so one link is correct there and a second link is exactly the hard-link attack this
            # check exists to catch.
            expected_links = 1 if os.name == "nt" else 0
            if os.fstat(descriptor).st_nlink != expected_links:
                retained = discard_private_staging(descriptor, staging_name, codex_home)
                print(
                    f"CODEX_GUIDANCE_STAGING_LINKED target={target} "
                    f"staging_retained={retained}"
                )
                return 1

            try:
                publish_private_staging(target, descriptor, directory_fd, staging_name)
            except FileExistsError:
                retained = discard_private_staging(descriptor, staging_name, codex_home)
                if retained:
                    print(f"CODEX_GUIDANCE_EXISTS_STAGING_RETAINED target={target}")
                    return 1
                print(f"CODEX_GUIDANCE_EXISTS target={target}")
                print("No existing Codex rule file was changed.")
                return 0
            except (AtomicPublishUnsupportedError, OSError) as error:
                retained = discard_private_staging(descriptor, staging_name, codex_home)
                print(
                    f"CODEX_GUIDANCE_PUBLISH_FAILED target={target} "
                    f"reason={type(error).__name__} staging_retained={retained}"
                )
                return 1
            public_target_created = True

            # A third override check covers creation concurrent with publication.
            if entry_exists(codex_home, "AGENTS.override.md", directory_fd):
                if os.name == "nt":
                    # The rollback used to ride on the staging descriptor carrying a
                    # delete-pending disposition, which removed the published entry when the
                    # handle closed. Windows staging is a named file now, so the published
                    # target is removed by name after the handle is closed. The override is
                    # already present at this point, which is exactly the condition under which
                    # the installer must not leave a published AGENTS.md behind it.
                    try:
                        _windows_discard_descriptor(descriptor)
                    except OSError as error:
                        print(
                            f"CODEX_GUIDANCE_FINALIZE_INCOMPLETE target={target} "
                            f"reason={type(error).__name__}"
                        )
                        return 1
                    try:
                        target.unlink()
                    except FileNotFoundError:
                        pass
                    except OSError as error:
                        print(
                            f"CODEX_GUIDANCE_OVERRIDE_AFTER_PUBLICATION target={target} "
                            f"reason={type(error).__name__}"
                        )
                        print("A complete public target remains; inspect it before retrying.")
                        return 1
                    print(f"CODEX_GUIDANCE_OVERRIDE_AFTER_PUBLICATION_ROLLED_BACK target={target}")
                    print("The complete public target was removed after the override appeared.")
                    return 1
                try:
                    os.close(descriptor)
                except OSError as error:
                    print(
                        f"CODEX_GUIDANCE_FINALIZE_INCOMPLETE target={target} "
                        f"reason={type(error).__name__}"
                    )
                    return 1
                print(f"CODEX_GUIDANCE_OVERRIDE_AFTER_PUBLICATION target={target}")
                print("A complete public target remains; inspect it before retrying.")
                return 1

            if not home_identity_matches(codex_home, directory_fd):
                os.close(descriptor)
                print(f"CODEX_GUIDANCE_HOME_CHANGED target={target} public_target_created=True")
                return 1

            if not public_target_matches(target, descriptor, directory_fd):
                os.close(descriptor)
                print(f"CODEX_GUIDANCE_PUBLIC_TARGET_CHANGED target={target}")
                return 1

            try:
                os.close(descriptor)
            except OSError as error:
                print(
                    f"CODEX_GUIDANCE_FINALIZE_INCOMPLETE target={target} "
                    f"reason={type(error).__name__}"
                )
                print("The target may be complete, but finalization was not verified; inspect it manually.")
                return 1

    except DirectoryFinalizeError as error:
        print(
            f"CODEX_GUIDANCE_DIRECTORY_FINALIZE_INCOMPLETE target={target} "
            f"reason={type(error.__cause__).__name__}"
        )
        return 1
    except CleanupIncompleteError as error:
        print(f"CODEX_GUIDANCE_CLEANUP_INCOMPLETE target={target} reason={type(error.__cause__).__name__}")
        print("A private or public installer object may remain; inspect it before retrying.")
        return 1
    except OSError as error:
        if staging_created or public_target_created:
            print(f"CODEX_GUIDANCE_FINALIZE_INCOMPLETE target={target} reason={type(error).__name__}")
            print("An installer object may remain; inspect it before retrying.")
            return 1
        print(f"CODEX_GUIDANCE_DIRECTORY_PIN_FAILED target={target} reason={type(error).__name__}")
        print("No existing Codex rule file was changed.")
        return 1
    print(f"CODEX_GUIDANCE_WRITTEN target={target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
