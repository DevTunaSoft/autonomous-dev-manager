"""Bounded, offline, non-executing packaged application smoke test.

This verifies bundled imports, local writable state and SQLite, but never
runs queued commands or generated code. Writes atomic JSON for --windowed EXEs.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile
import time


def smoke_report():
    checks = {}
    for name in ('adm.desktop', 'adm.daemon', 'adm.worker', 'adm.ollama_direct', 'adm.model_selection'):
        try:
            __import__(name)
            checks['import:' + name] = 'passed'
        except Exception as exc:
            checks['import:' + name] = f'failed: {type(exc).__name__}: {exc}'
    try:
        from adm.worker import WorkerSupervisor
        with tempfile.TemporaryDirectory(prefix='adm-smoke-') as temp:
            worker = WorkerSupervisor(temp)
            try:
                count = worker.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
                checks['sqlite_wal_and_schema'] = 'passed' if count == 0 else 'failed: unexpected jobs'
            finally:
                worker.close()
    except Exception as exc:
        checks['sqlite_wal_and_schema'] = f'failed: {type(exc).__name__}: {exc}'
    return {'format': 'ADM-packaged-smoke-v1', 'timestamp': time.time(),
            'checks': checks, 'passed': bool(checks) and all(v == 'passed' for v in checks.values()),
            'scope': 'imports and SQLite only; NOT a Windows GUI, sandbox, AI or end-to-end acceptance test'}


def write_smoke_report(destination):
    target = Path(destination).resolve()
    if not target.parent.is_dir():
        raise ValueError('Smoke report parent directory must exist')
    report = smoke_report()
    fd, temporary = tempfile.mkstemp(prefix='.adm-smoke-', suffix='.tmp', dir=str(target.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return report
