# SPDX-License-Identifier: MIT
"""Non-expiring OS-owned lock for publication-only native recovery workers."""
from contextlib import contextmanager
import hashlib
import os


class RecoveryBusy(RuntimeError):
    pass


@contextmanager
def recovery_lock(paths, attempt_id):
    if not isinstance(attempt_id, str) or not attempt_id or len(attempt_id) > 256:
        raise ValueError('invalid recovery identity')
    name = hashlib.sha256(attempt_id.encode('utf-8')).hexdigest() + '.lock'
    path = paths.category_dir('runtime', 'native-recovery-locks', name)
    path.parent.mkdir(parents=True, exist_ok=True)
    paths.checked_path(path)
    # Never unlink this file: replacing the inode could split lock ownership.
    with path.open('a+b') as stream:
        if os.fstat(stream.fileno()).st_nlink != 1:
            raise ValueError('recovery lock must not be hardlinked')
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RecoveryBusy('native recovery worker is active or lock unavailable') from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
