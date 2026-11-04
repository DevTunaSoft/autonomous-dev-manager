"""Crash-released OS file lock for exclusive project ownership.

The lock file persists; ownership is a kernel lock on byte zero, never a
file-existence check. Windows uses msvcrt.locking, POSIX uses flock.
This is NOT a sandbox and does not prevent malicious processes from editing.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import time
from .engine import SafetyError


# Windows byte-range locks are MANDATORY: other handles cannot read the locked
# bytes. Lock a byte far beyond the JSON metadata so owner info stays readable.
_WINDOWS_LOCK_OFFSET = 1 << 30


def _acquire(stream):
    stream.seek(_WINDOWS_LOCK_OFFSET if os.name == 'nt' else 0)
    if os.name == 'nt':
        import msvcrt
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise SafetyError('Project is already owned by another supervisor') from exc
    else:
        import fcntl
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise SafetyError('Project is already owned by another supervisor') from exc


def _release(stream):
    stream.seek(_WINDOWS_LOCK_OFFSET if os.name == 'nt' else 0)
    if os.name == 'nt':
        import msvcrt
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def exclusive_project(root):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise SafetyError('Project root is not a directory')
    lock = root / '.adm-repair.lock'
    if lock.is_symlink():
        raise SafetyError('Refusing symlink lock file')
    # Do not unlink this file: removing/recreating it can split ownership
    # across different inodes. Kernel lock is released on process death.
    with open(lock, 'a+b') as stream:
        if lock.is_symlink():
            raise SafetyError('Refusing symlink lock file')
        _acquire(stream)
        record = {'version': 2, 'pid': os.getpid(), 'created_unix': time.time(),
                  'root': str(root), 'token': secrets.token_hex(24)}
        try:
            stream.seek(0)
            stream.truncate()
            stream.write(json.dumps(record, sort_keys=True).encode('utf-8'))
            stream.flush()
            os.fsync(stream.fileno())
            yield record
        finally:
            _release(stream)
