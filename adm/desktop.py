"""Small dependency-free desktop control panel for ADM.

Tkinter is supplied by many Python installations but must be verified on target
Windows. This panel lets a person start a request and watch the background worker;
it is not itself an untrusted-code sandbox.
"""
from __future__ import annotations
import sqlite3
import os
from pathlib import Path
import subprocess
import sys
import time
from .daemon import read_status, request_stop


def status_summary(state, *, now=None, stale_after=15):
    """Return an honest state; a stale heartbeat is never reported as running."""
    record = read_status(state)
    name = record.get('state', 'unknown')
    if name == 'running':
        stamp = record.get('heartbeat_at')
        current = time.time() if now is None else now
        if not isinstance(stamp, (int, float)) or stamp > current + 30 or current - stamp > stale_after:
            name = 'unresponsive'
    return {'state': name, 'pid': record.get('pid'), 'cycles': record.get('cycles', 0),
            'last_result': record.get('last_result'), 'heartbeat_at': record.get('heartbeat_at')}


def launch_supervisor(state, *, executable=None, frozen=None):
    """Start a detached supervisor; avoid duplicate starts on fresh heartbeats."""
    state = Path(state).resolve()
    if status_summary(state)['state'] == 'running':
        return {'started': False, 'reason': 'Supervisor already reports a fresh heartbeat'}
    state.mkdir(parents=True, exist_ok=True)
    if frozen is None:
        frozen = bool(getattr(sys, 'frozen', False))
    if frozen:
        cmd = [str(executable or sys.executable), '--adm-supervisor', '--state', str(state)]
    else:
        cmd = [str(executable or sys.executable), '-m', 'adm.daemon', '--state', str(state)]
    kwargs = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL,
              'stderr': subprocess.DEVNULL, 'cwd': str(state)}
    if not frozen:
        env = os.environ.copy()
        project_root = str(Path(__file__).resolve().parent.parent)
        env['PYTHONPATH'] = os.pathsep.join(filter(None, [project_root, env.get('PYTHONPATH', '')]))
        kwargs['env'] = env
    if os.name == 'nt':
        kwargs['creationflags'] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs['start_new_session'] = True
    proc = subprocess.Popen(cmd, **kwargs)
    return {'started': True, 'pid': proc.pid}


def recent_jobs(state, limit=30):
    """Read-only snapshot; never create/claim/execute a queued job from GUI."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError('limit must be 1..100')
    database = Path(state).resolve() / 'jobs.sqlite'
    if not database.is_file():
        return []
    # Read-only SQLite URI prevents creating a missing database by accident.
    from urllib.parse import quote
    uri = 'file:' + quote(str(database), safe='/\\:') + '?mode=ro'
    connection = sqlite3.connect(uri, uri=True, timeout=1)
    try:
        connection.execute('PRAGMA query_only=ON')
        columns = {r[1] for r in connection.execute('PRAGMA table_info(jobs)')}
        note_column = 'error' if 'error' in columns else "''"
        rows = connection.execute(
            f'SELECT id,label,state,attempts,exit_code,{note_column} FROM jobs ORDER BY id DESC LIMIT ?',
            (limit,)).fetchall()
        return [{'id': row[0], 'label': row[1], 'state': row[2],
                 'attempts': row[3], 'exit_code': row[4],
                 'note': (row[5] or '')[:200]} for row in rows]
    finally:
        connection.close()


def main(*, auto_close_ms=None, ask=None):
    """The ADM main window is the dark dashboard; this delegates to it."""
    from .dashboard import main as dashboard_main
    return dashboard_main(auto_close_ms=auto_close_ms, ask=ask)


if __name__ == '__main__':
    main()
