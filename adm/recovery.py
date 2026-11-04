"""Bounded, verified workspace snapshot/restore for disposable repair trials.

Not a sandbox or a replacement for Git. Refuses symlinks and oversized workspaces.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil

from .engine import SafetyError, inside

EXCLUDE = {'__pycache__', '.pytest_cache', '.git', '.venv', 'venv', '.mypy_cache'}
MAX_FILES = 500
MAX_BYTES = 30 * 1024 * 1024


def inventory(root: Path) -> dict[str, str]:
    root = Path(root).resolve()
    found = {}
    total = 0
    for current, dirs, files in os.walk(root, followlinks=False):
        base = Path(current)
        dirs[:] = [d for d in dirs if d not in EXCLUDE]   # excluded trees (venv, .git) are never inspected
        for name in [*dirs, *files]:
            if (base / name).is_symlink():
                raise SafetyError('Symlink in workspace: refusing snapshot or restore')
        for name in files:
            item = base / name
            if not item.is_file():
                raise SafetyError('Workspace contains a non-regular file')
            total += item.stat().st_size
            if total > MAX_BYTES or len(found) >= MAX_FILES:
                raise SafetyError('Workspace exceeds safe snapshot limits')
            found[item.relative_to(root).as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    return dict(sorted(found.items()))


def save_snapshot(root: Path, dest: Path) -> dict[str, str]:
    root, dest = Path(root).resolve(), Path(dest).resolve()
    if inside(dest, root) or inside(root, dest):
        raise SafetyError('Backup must be separate from project')
    if dest.exists():
        raise SafetyError('Snapshot already exists; refusing overwrite')
    hashes = inventory(root)
    dest.mkdir(parents=True)
    for rel in hashes:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, target)
    if inventory(dest) != hashes:
        raise SafetyError('Snapshot copy verification failed')
    return hashes


def restore_snapshot(root: Path, dest: Path, expected: dict[str, str]) -> None:
    """Restore contents after an interrupted agent; retain only pre-attempt files.

    Only call when the worker has exited. Cannot protect against concurrent writers.
    """
    root, dest = Path(root).resolve(), Path(dest).resolve()
    if inside(dest, root) or inside(root, dest) or not dest.is_dir():
        raise SafetyError('Unsafe or absent snapshot')
    if inventory(dest) != expected:
        raise SafetyError('Snapshot damaged or altered; intervention required')
    current = inventory(root)
    for rel in current.keys() - expected.keys():
        (root / rel).unlink()
    for rel in expected:
        source, target = dest / rel, root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    if inventory(root) != expected:
        raise SafetyError('Restore verification failed')
