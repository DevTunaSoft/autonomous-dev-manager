"""Small dependency-free desktop control panel for the trusted-job supervisor.

Tkinter is supplied by many Python installations but must be verified on target
Windows. This is a control panel, not an untrusted-code sandbox or AI builder.
"""
from __future__ import annotations
import json
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
        rows = connection.execute(
            'SELECT id,label,state,attempts,exit_code FROM jobs ORDER BY id DESC LIMIT ?',
            (limit,)).fetchall()
        return [{'id': row[0], 'label': row[1], 'state': row[2],
                 'attempts': row[3], 'exit_code': row[4]} for row in rows]
    finally:
        connection.close()


def main():
    import tkinter as tk
    from tkinter import messagebox
    state = Path.home() / 'AppData' / 'Local' / 'ADM' / 'state' if os.name == 'nt' else Path.home() / '.adm-worker-state'
    window = tk.Tk()
    window.title('Autonomous Development Manager — Prototype')
    window.geometry('760x540')
    heading = tk.Label(window, text='Autonomous Development Manager', font=('Segoe UI', 17, 'bold'))
    heading.pack(pady=(18, 8))
    tk.Label(window, text='Trusted-job supervisor control panel (not yet a complete AI builder)').pack()
    status = tk.StringVar(value='Checking supervisor...')
    tk.Label(window, textvariable=status, font=('Segoe UI', 12)).pack(pady=20)
    buttons = tk.Frame(window)
    buttons.pack()
    def start():
        try:
            result = launch_supervisor(state)
            if not result['started']:
                messagebox.showinfo('Already running', result['reason'])
        except Exception as exc:
            messagebox.showerror('Unable to start', str(exc))
        refresh()
    def stop():
        request_stop(state)
        refresh()
    tk.Button(buttons, text='Start supervisor', command=start, width=20).pack(side='left', padx=8)
    tk.Button(buttons, text='Stop supervisor', command=stop, width=20).pack(side='left', padx=8)
    tk.Label(window, text='Trusted jobs only. Generated code is NOT sandboxed. Windows validation pending.',
             wraplength=700).pack(pady=12)
    from tkinter import ttk
    table = ttk.Treeview(window, columns=('id','label','state','attempts','exit'), show='headings', height=9)
    for name, width in [('id',65),('label',250),('state',130),('attempts',90),('exit',80)]:
        table.heading(name, text=name.title())
        table.column(name, width=width, stretch=(name == 'label'))
    table.pack(fill='both', expand=True, padx=18, pady=8)
    model_status = tk.StringVar(value='Ollama: not checked')
    tk.Label(window, textvariable=model_status, wraplength=700).pack(pady=5)
    def check_models():
        # Network check runs off the UI thread; Tk updates only on main thread.
        import threading
        def check():
            try:
                from .ollama_health import inspect_ollama
                result = inspect_ollama(timeout=3)
                message = 'Ollama reachable; installed models: ' + ', '.join(result['installed_models'][:5])
                if not result['installed_models']:
                    message = 'Ollama reachable; no models installed'
            except Exception as exc:
                message = 'Ollama unavailable: ' + str(exc)
            try:
                window.after(0, lambda: model_status.set(message))
            except RuntimeError:
                pass
        threading.Thread(target=check, daemon=True).start()
    tk.Button(window, text='Check local Ollama', command=check_models).pack(pady=5)
    def refresh():
        data = status_summary(state)
        status.set(f"Status: {data['state']}   |   Supervisor cycles: {data['cycles']}")
        try:
            records = recent_jobs(state)
            table.delete(*table.get_children())
            for job in records:
                table.insert('', 'end', values=(job['id'], job['label'], job['state'],
                                                job['attempts'], job['exit_code']))
        except (OSError, sqlite3.Error, ValueError) as exc:
            status.set('Unable to read queue: ' + str(exc))
    def tick():
        refresh()
        window.after(2000, tick)
    tick()
    window.mainloop()

if __name__ == '__main__':
    main()
