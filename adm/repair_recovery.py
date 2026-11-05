"""Crash journal for local-model source replacements.

A repair job must be stopped before recovery; this module does not kill workers.
Recovery is deliberately conservative: restore only when every current file is
identical to either its recorded original or its recorded replacement.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
from .engine import SafetyError
from .context import patch_files


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _write_atomic(path, data):
    fd, temp = tempfile.mkstemp(prefix='.adm-restore-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def prepare_journal(root, evidence, patch):
    """Persist original and proposed bytes before any application source is edited."""
    root, evidence = Path(root).resolve(), Path(evidence).resolve()
    journal = evidence / 'repair-journal.json'
    if journal.exists():
        raise SafetyError('Unresolved repair journal; recovery required')
    entries = []
    for item in patch_files(patch):          # validate the (untrusted) patch shape first
        name = item['path']
        target = root / name
        if (Path(name).name != name or not name.endswith('.py') or name.startswith('test_')
                or not target.is_file() or target.is_symlink()):
            raise SafetyError('Unsafe repair journal target')
        original = target.read_bytes()
        replacement = item['content'].encode('utf-8')
        entries.append({'path': name, 'original_b64': base64.b64encode(original).decode('ascii'),
                        'original_sha256': _digest(original), 'replacement_sha256': _digest(replacement)})
    evidence.mkdir(parents=True, exist_ok=True)
    data = json.dumps({'version': 1, 'root': str(root), 'entries': entries}, sort_keys=True).encode()
    _write_atomic(journal, data)
    return journal


def recover_journal(root, evidence):
    """Restore an interrupted attempt; refuse unexpected edits or symlink substitutions."""
    root, evidence = Path(root).resolve(), Path(evidence).resolve()
    journal = evidence / 'repair-journal.json'
    if not journal.exists():
        return False
    try:
        doc = json.loads(journal.read_text(encoding='utf-8'))
    except (OSError, ValueError, RecursionError) as exc:
        raise SafetyError('Repair journal is unreadable') from exc
    if not isinstance(doc, dict) or doc.get('version') != 1 or doc.get('root') != str(root) \
            or not isinstance(doc.get('entries'), list):
        raise SafetyError('Invalid repair journal or project mismatch')
    originals = []
    seen = set()
    for entry in doc['entries']:
        if not isinstance(entry, dict) or not all(isinstance(entry.get(k), str) for k in
                ('path', 'original_b64', 'original_sha256', 'replacement_sha256')):
            raise SafetyError('Malformed repair journal entry')
        name = entry['path']
        path = root / name
        if (name in seen or Path(name).name != name or not name.endswith('.py')
                or name.startswith('test_') or not path.is_file() or path.is_symlink()):
            raise SafetyError('Unsafe or missing recovery target')
        seen.add(name)
        try:
            old = base64.b64decode(entry['original_b64'], validate=True)
        except Exception as exc:
            raise SafetyError('Repair journal has invalid encoded data') from exc
        current = path.read_bytes()
        if _digest(old) != entry['original_sha256'] or _digest(current) not in (
                entry['original_sha256'], entry['replacement_sha256']):
            raise SafetyError('Recovery blocked: unexpected source change')
        originals.append((path, old))
    for path, old in originals:
        _write_atomic(path, old)
    journal.unlink()
    return True


def finish_journal(evidence):
    (Path(evidence) / 'repair-journal.json').unlink(missing_ok=True)
