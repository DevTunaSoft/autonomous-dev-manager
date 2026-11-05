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


def _legacy_control_panel(*, auto_close_ms=None, ask=None):
    import tkinter as tk
    from tkinter import ttk, messagebox
    from . import theme
    state = Path.home() / 'AppData' / 'Local' / 'ADM' / 'state' if os.name == 'nt' else Path.home() / '.adm-worker-state'
    window = tk.Tk()
    window.title('Autonomous Development Manager')
    window.geometry('800x650')
    window.minsize(700, 620)
    theme.apply(window)

    theme.header(window, 'Autonomous Development Manager',
                 'Local, free AI that plans, builds and tests small apps for you').pack(fill='x')
    body = ttk.Frame(window, style='TFrame')
    body.pack(fill='both', expand=True, padx=24, pady=(16, 14))

    # --- Primary action -------------------------------------------------
    ttk.Label(body, text='Start here', style='Section.TLabel').pack(anchor='w')
    cta = ttk.Frame(body, style='TFrame')
    cta.pack(fill='x', pady=(6, 2))

    def new_request():
        from .intake_gui import open_request_window
        open_request_window(window, state)
    ttk.Button(cta, text='＋   New request', style='Primary.TButton', command=new_request).pack(side='left')
    ttk.Label(cta, text='Describe an app in plain words. ADM writes a plan for you to approve.',
              style='Muted.TLabel').pack(side='left', padx=12)

    # --- Local AI -------------------------------------------------------
    ttk.Label(body, text='Local AI', style='Section.TLabel').pack(anchor='w', pady=(16, 0))
    ai_row = ttk.Frame(body, style='TFrame')
    ai_row.pack(fill='x', pady=(6, 2))
    setup_status = tk.StringVar(value='Local AI: not checked yet')
    busy = {'setup': False}

    def say(text):
        try:
            window.after(0, lambda: setup_status.set(text))
        except RuntimeError:
            pass

    def setup_flow(*, prompt_only_if_missing):
        if busy['setup']:
            return
        busy['setup'] = True
        import threading
        def work():
            from . import firstrun
            try:
                a = firstrun.assess()
            except Exception as exc:
                busy['setup'] = False
                say('Local AI: could not check (' + str(exc) + ')')
                return
            def decide():
                title, message = firstrun.prompt_text(a)
                if a['ready']:
                    say('Local AI ready: ' + str(a['usable_model']))
                    busy['setup'] = False
                    if not prompt_only_if_missing:
                        messagebox.showinfo(title, message)
                    return
                can_act = bool({'ollama', 'start_ollama', 'model'} & set(a['needs']))
                say('Local AI needs setup: ' + ', '.join(a['needs']))
                yes = (ask or messagebox.askyesno)(title, message) if can_act else (messagebox.showinfo(title, message) and False)
                if not yes:
                    busy['setup'] = False
                    return
                def install():
                    try:
                        result = firstrun.run_setup(a, approved=True, on_status=say)
                    except Exception as exc:
                        result = {'status': 'failed', 'message': str(exc)}
                    busy['setup'] = False
                    say('Local AI: ' + result['message'])
                    window.after(0, lambda: messagebox.showinfo('Local AI setup', result['message']))
                threading.Thread(target=install, daemon=True).start()
            try:
                window.after(0, decide)
            except RuntimeError:
                pass
        threading.Thread(target=work, daemon=True).start()

    ttk.Button(ai_row, text='Set up local AI…', style='Secondary.TButton',
               command=lambda: setup_flow(prompt_only_if_missing=False)).pack(side='left')
    ttk.Label(ai_row, textvariable=setup_status, style='Muted.TLabel', wraplength=520,
              justify='left').pack(side='left', padx=12)

    # --- Background worker ---------------------------------------------
    ttk.Label(body, text='Background worker', style='Section.TLabel').pack(anchor='w', pady=(16, 0))
    status = tk.StringVar(value='Checking…')
    ttk.Label(body, textvariable=status, style='TLabel').pack(anchor='w', pady=(4, 6))

    def start():
        try:
            result = launch_supervisor(state)
            if not result['started']:
                messagebox.showinfo('Already running', result['reason'])
        except Exception as exc:
            messagebox.showerror('Unable to start', str(exc))
        refresh()

    def stop():
        if status_summary(state)['state'] in ('running', 'unresponsive'):
            request_stop(state)
        else:
            messagebox.showinfo('Not running', 'The background worker is not running.')
        refresh()

    worker_row = ttk.Frame(body, style='TFrame')
    worker_row.pack(fill='x')
    ttk.Button(worker_row, text='Start', style='Secondary.TButton', command=start).pack(side='left')
    ttk.Button(worker_row, text='Stop', style='Secondary.TButton', command=stop).pack(side='left', padx=8)

    table = ttk.Treeview(body, columns=('id', 'label', 'state', 'attempts', 'exit', 'note'),
                         show='headings', height=3)
    for name, title, width in [('id', 'ID', 55), ('label', 'Job', 220), ('state', 'State', 120),
                               ('attempts', 'Tries', 60), ('exit', 'Exit', 55), ('note', 'Why / note', 280)]:
        table.heading(name, text=title)
        table.column(name, width=width, stretch=(name in ('label', 'note')),
                     anchor='w' if name in ('label', 'note', 'state') else 'center')
    table.pack(fill='x', expand=False, pady=(10, 10))

    ttk.Label(body, text='Early build: ADM can plan a project today. Writing and running code is being '
              'added next, and when it runs it runs in a locked-down sandbox with no internet.',
              style='Muted.TLabel', wraplength=720, justify='left').pack(anchor='w', pady=(2, 0))

    def refresh():
        data = status_summary(state)
        status.set(f"Status: {data['state']}    ·    cycles: {data['cycles']}")
        try:
            records = recent_jobs(state)
            table.delete(*table.get_children())
            for job in records:
                table.insert('', 'end', values=(job['id'], job['label'], job['state'],
                                                job['attempts'], job['exit_code'], job['note']))
        except (OSError, sqlite3.Error, ValueError) as exc:
            status.set('Unable to read queue: ' + str(exc))

    def tick():
        refresh()
        window.after(2000, tick)
    tick()
    window.after(800, lambda: setup_flow(prompt_only_if_missing=True))   # first-run prompt
    if auto_close_ms:
        window.after(auto_close_ms, window.destroy)
    window.mainloop()


if __name__ == '__main__':
    main()
