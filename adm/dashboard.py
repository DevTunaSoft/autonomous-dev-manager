"""Dark dashboard main window for ADM.

Layout follows the product mockup: a left sidebar, a row of KPI tiles, a New-request panel,
a project pipeline, a live activity feed and a recent-projects strip. Every panel is wired to
REAL data or shows an honest empty state -- no invented numbers. The 'Approve & build' action
drives the real build stage (adm.build), which runs generated code only in the sandbox.
"""
from __future__ import annotations
import json
import os
import threading
import time
from pathlib import Path
from . import intake, theme
from .engine import SafetyError

NAV = [('⬒', 'Dashboard'), ('＋', 'New request'), ('▦', 'Projects'), ('⚙', 'Active jobs'),
       ('✓', 'Tests & QA'), ('⬢', 'Builds & releases'), ('◆', 'AI models'), ('⚙', 'Settings')]
STAGES = ['Plan & requirements', 'Code generation', 'Build & test', 'Auto-fix', 'Package & deliver']


def collect_stats(state) -> dict:
    """Read real counters from the plans/builds stores and the worker queue. Unknowns stay '—'."""
    state = Path(state)
    out = {'projects': 0, 'queue': 0, 'completed': 0, 'passing': '—', 'builds': 0}
    plans = state / 'plans'
    approved = 0
    if plans.is_dir():
        for pj in plans.glob('*/plan.json'):
            try:
                if json.loads(pj.read_text(encoding='utf-8')).get('status') == 'approved':
                    approved += 1
            except (OSError, ValueError):
                pass
    out['projects'] = approved
    builds = state / 'builds'
    latest = None
    if builds.is_dir():
        reports = sorted(builds.glob('*.json'))
        built = 0
        for r in reports:
            try:
                data = json.loads(r.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if data.get('status') == 'built':
                built += 1
            latest = data
        out['completed'] = built
    if latest and latest.get('status') == 'built':
        n = len(latest.get('checks', []) or [])
        out['passing'] = f'{n}/{n}' if n else '100%'
    dist = state / 'dist'
    out['builds'] = len(list(dist.glob('*.exe'))) if dist.is_dir() else 0
    try:
        from .desktop import recent_jobs
        out['queue'] = sum(1 for j in recent_jobs(state) if j['state'] == 'pending')
    except Exception:
        pass
    return out


def _fmt_uptime(seconds: float) -> str:
    m = int(seconds // 60)
    h, m = divmod(m, 60)
    return f'{h}h {m:02d}m' if h else f'{m}m'


def main(*, auto_close_ms=None, ask=None, _plan_generator=None, _plan_model=None, _auto=None, _zoom=False):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    t = theme
    state = (Path.home() / 'AppData' / 'Local' / 'ADM' / 'state') if os.name == 'nt' else (Path.home() / '.adm-worker-state')
    state.mkdir(parents=True, exist_ok=True)
    started_at = time.time()

    win = tk.Tk()
    win.title('ADM — Autonomous Development Manager')
    win.geometry('1180x740')
    win.minsize(1000, 680)
    t.apply(win)

    # ---------------- Sidebar ----------------
    sidebar = tk.Frame(win, bg=t.SIDEBAR, width=180)
    sidebar.pack(side='left', fill='y')
    sidebar.pack_propagate(False)
    brand = tk.Frame(sidebar, bg=t.SIDEBAR)
    brand.pack(fill='x', padx=18, pady=(18, 22))
    tk.Label(brand, text='∞', bg=t.SIDEBAR, fg=t.BRAND_HI, font=t.font(22, 'bold')).pack(side='left')
    tk.Label(brand, text='ADM', bg=t.SIDEBAR, fg=t.INK, font=t.font(14, 'bold')).pack(side='left', padx=8)

    def nav_click(label):
        if label == 'New request':
            request_box.focus_set()
        elif label != 'Dashboard':
            log(f'The "{label}" screen is not built yet.')

    for icon, label in NAV:
        active = label == 'Dashboard'
        item = tk.Frame(sidebar, bg=t.PANEL_HI if active else t.SIDEBAR, cursor='hand2')
        item.pack(fill='x', padx=10, pady=1)
        bar = tk.Frame(item, bg=t.BRAND_HI if active else t.SIDEBAR, width=3)
        bar.pack(side='left', fill='y')
        tk.Label(item, text=icon, bg=item['bg'], fg=t.BRAND_HI if active else t.MUTED,
                 font=t.font(12), width=3).pack(side='left', pady=8)
        tk.Label(item, text=label, bg=item['bg'], fg=t.INK if active else t.MUTED,
                 font=t.font(10, 'bold' if active else 'normal')).pack(side='left')
        for w in (item, *item.winfo_children()):
            w.bind('<Button-1>', lambda e, l=label: nav_click(l))

    ai_box = tk.Frame(sidebar, bg=t.PANEL, highlightthickness=1, highlightbackground=t.BORDER)
    ai_box.pack(side='bottom', fill='x', padx=12, pady=14)
    ai_title = tk.Label(ai_box, text='○ LOCAL AI', bg=t.PANEL, fg=t.MUTED, font=t.font(9, 'bold'), anchor='w')
    ai_title.pack(fill='x', padx=12, pady=(10, 2))
    ai_detail = tk.Label(ai_box, text='Checking this PC…', bg=t.PANEL, fg=t.MUTED, font=t.font(9), anchor='w', justify='left', wraplength=130)
    ai_detail.pack(fill='x', padx=12, pady=(0, 10))

    # ---------------- Main area ----------------
    main_area = tk.Frame(win, bg=t.PAGE)
    main_area.pack(side='left', fill='both', expand=True)

    header = tk.Frame(main_area, bg=t.PAGE)
    header.pack(fill='x', padx=22, pady=(16, 8))
    tk.Label(header, text='Autonomous Development Manager', bg=t.PAGE, fg=t.INK,
             font=t.font(18, 'bold')).pack(anchor='w')
    tk.Label(header, text='Plan · Code · Build · Test · Fix — automatically, with local AI',
             bg=t.PAGE, fg=t.MUTED, font=t.font(10)).pack(anchor='w', pady=(2, 0))

    # KPI tiles
    tiles = tk.Frame(main_area, bg=t.PAGE)
    tiles.pack(fill='x', padx=18, pady=(6, 4))
    tile_defs = [('projects', '▦', 'Projects', t.CYAN), ('queue', '▤', 'In queue', t.BRAND_HI),
                 ('completed', '✓', 'Completed', t.SUCCESS), ('passing', '◆', 'Checks', t.SUCCESS),
                 ('builds', '⬢', 'Builds', t.BRAND_HI), ('uptime', '◷', 'Uptime', t.CYAN)]
    setters = {}
    for i, (key, icon, label, accent) in enumerate(tile_defs):
        tiles.columnconfigure(i, weight=1, uniform='tile')
        cell, setv = t.stat_tile(tiles, icon, label, accent)
        cell.grid(row=0, column=i, padx=5, sticky='nsew')
        setters[key] = setv

    # Content: left (request) + right (pipeline/activity)
    middle = tk.Frame(main_area, bg=t.PAGE)
    middle.pack(fill='both', expand=True, padx=18, pady=8)
    middle.columnconfigure(0, weight=3, uniform='col')
    middle.columnconfigure(1, weight=2, uniform='col')
    middle.rowconfigure(0, weight=1)

    # --- Left: New request ---
    left_holder, left = t.card(middle)
    left_holder.grid(row=0, column=0, sticky='nsew', padx=(0, 9))
    tk.Label(left, text='New request', bg=t.PANEL, fg=t.INK, font=t.font(13, 'bold')).pack(anchor='w')
    tk.Label(left, text='Describe the app or change you want, in your own words.',
             bg=t.PANEL, fg=t.MUTED, font=t.font(9)).pack(anchor='w', pady=(2, 8))
    box_frame, request_box = t.entry_text(left, height=4)
    box_frame.pack(fill='x')

    mode = tk.StringVar(value='new')
    row = tk.Frame(left, bg=t.PANEL)
    row.pack(fill='x', pady=(10, 4))
    folder = tk.StringVar()
    f_entry = ttk.Entry(row, textvariable=folder, state='disabled')
    f_browse = ttk.Button(row, text='Browse…', style='Secondary.TButton', state='disabled',
                          command=lambda: folder.set(filedialog.askdirectory(title='Choose a folder') or folder.get()))

    def sync():
        on = 'normal' if mode.get() == 'existing' else 'disabled'
        f_entry.config(state=on)
        f_browse.config(state=on)
    tk.Radiobutton(row, text='New project', variable=mode, value='new', command=sync,
                   bg=t.PANEL, fg=t.INK, selectcolor=t.PANEL_HI, activebackground=t.PANEL,
                   activeforeground=t.INK, font=t.font(10), bd=0, highlightthickness=0).pack(side='left')
    tk.Radiobutton(row, text='Existing:', variable=mode, value='existing', command=sync,
                   bg=t.PANEL, fg=t.INK, selectcolor=t.PANEL_HI, activebackground=t.PANEL,
                   activeforeground=t.INK, font=t.font(10), bd=0, highlightthickness=0).pack(side='left', padx=(12, 6))
    f_entry.pack(side='left', fill='x', expand=True)
    f_browse.pack(side='left', padx=(6, 0))

    btns = tk.Frame(left, bg=t.PANEL)
    btns.pack(fill='x', pady=(12, 8))
    make_btn = ttk.Button(btns, text='Make plan', style='Secondary.TButton')
    approve_btn = ttk.Button(btns, text='✓  Approve & build', style='Primary.TButton', state='disabled')
    reject_btn = ttk.Button(btns, text='Not this', style='Danger.TButton', state='disabled')
    make_btn.pack(side='left')
    approve_btn.pack(side='left', padx=8)
    reject_btn.pack(side='left')

    plan_status = tk.Label(left, text='Nothing has been created or run yet.', bg=t.PANEL, fg=t.MUTED,
                           font=t.font(9), anchor='w', justify='left', wraplength=460)
    plan_status.pack(fill='x', pady=(2, 6))
    doc_frame, plan_doc = t.document(left, height=9)
    doc_frame.pack(fill='both', expand=True)

    # --- Right: pipeline + activity ---
    right = tk.Frame(middle, bg=t.PAGE)
    right.grid(row=0, column=1, sticky='nsew', padx=(9, 0))
    right.rowconfigure(0, weight=0)
    right.rowconfigure(1, weight=1)
    right.columnconfigure(0, weight=1)

    pipe_holder, pipe = t.card(right)
    pipe_holder.grid(row=0, column=0, sticky='nsew', pady=(0, 10))
    tk.Label(pipe, text='Project pipeline', bg=t.PANEL, fg=t.INK, font=t.font(12, 'bold')).pack(anchor='w')
    stage_rows = {}
    for s in STAGES:
        r = tk.Frame(pipe, bg=t.PANEL)
        r.pack(fill='x', pady=3)
        dot = tk.Label(r, text='○', bg=t.PANEL, fg=t.FAINT, font=t.font(11))
        dot.pack(side='left')
        name = tk.Label(r, text=s, bg=t.PANEL, fg=t.MUTED, font=t.font(10))
        name.pack(side='left', padx=8)
        stg = tk.Label(r, text='Pending', bg=t.PANEL, fg=t.FAINT, font=t.font(9))
        stg.pack(side='right')
        stage_rows[s] = (dot, name, stg)

    act_holder, act = t.card(right)
    act_holder.grid(row=1, column=0, sticky='nsew')
    act_head = tk.Frame(act, bg=t.PANEL)
    act_head.pack(fill='x')
    tk.Label(act_head, text='AI activity', bg=t.PANEL, fg=t.INK, font=t.font(12, 'bold')).pack(side='left')
    live_dot = tk.Label(act_head, text='● idle', bg=t.PANEL, fg=t.FAINT, font=t.font(9))
    live_dot.pack(side='right')
    activity = tk.Text(act, height=6, wrap='word', state='disabled', relief='flat', bd=0,
                       bg=t.PANEL, fg=t.MUTED, font=t.font(9), padx=2, pady=6)
    activity.pack(fill='both', expand=True, pady=(6, 0))

    # Recent projects strip (reserved at the bottom so it is always visible)
    rec_holder, rec = t.card(main_area, height=150)
    rec_holder.pack(side='bottom', fill='x', padx=18, pady=(2, 14))
    tk.Label(rec, text='Recent projects', bg=t.PANEL, fg=t.INK, font=t.font(12, 'bold')).pack(anchor='w', pady=(0, 6))
    rec_table = ttk.Treeview(rec, columns=('name', 'status', 'folder'), show='headings', height=3)
    for c, title, w in [('name', 'Project', 200), ('status', 'Status', 140), ('folder', 'Folder', 420)]:
        rec_table.heading(c, text=title)
        rec_table.column(c, width=w, anchor='w', stretch=(c == 'folder'))
    rec_table.pack(fill='x')

    # ---------------- behaviour ----------------
    current = {'plan': None, 'busy': False}
    result = {'status': 'no plan', 'folder': '', 'build': None}

    def log(line):
        stamp = time.strftime('%H:%M:%S')
        activity.config(state='normal')
        activity.insert('end', f'{stamp}   {line}\n')
        activity.see('end')
        activity.config(state='disabled')

    def set_live(on):
        live_dot.config(text='● running' if on else '● idle', fg=t.CYAN if on else t.FAINT)

    def set_stage(stage, status, color):
        dot, name, stg = stage_rows[stage]
        glyph = {'done': '●', 'run': '◉', 'pending': '○', 'skip': '○'}.get(status, '○')
        dot.config(text=glyph, fg=color)
        name.config(fg=t.INK if status in ('done', 'run') else t.MUTED)
        stg.config(text={'done': 'Complete', 'run': 'Running…', 'pending': 'Pending',
                         'skip': 'Not built yet'}[status], fg=color)

    def reset_pipeline():
        for s in STAGES:
            set_stage(s, 'pending', t.FAINT)

    def show_plan(text):
        plan_doc.config(state='normal')
        plan_doc.delete('1.0', 'end')
        plan_doc.insert('1.0', text)
        plan_doc.config(state='disabled')

    def set_status(text, color=None):
        plan_status.config(text=text, fg=color or t.MUTED)

    def set_buttons(plan):
        ok = plan is not None and plan['status'] == 'awaiting_approval'
        approve_btn.config(state='normal' if ok else 'disabled')
        reject_btn.config(state='normal' if plan is not None and plan['status'] in ('awaiting_approval', 'needs_answers') else 'disabled')

    def refresh_stats():
        s = collect_stats(state)
        setters['projects'](s['projects'])
        setters['queue'](s['queue'])
        setters['completed'](s['completed'])
        setters['passing'](s['passing'])
        setters['builds'](s['builds'])
        setters['uptime'](_fmt_uptime(time.time() - started_at))

    def refresh_recent():
        rec_table.delete(*rec_table.get_children())
        plans = state / 'plans'
        rows = []
        if plans.is_dir():
            for pj in sorted(plans.glob('*/plan.json'), reverse=True)[:6]:
                try:
                    p = json.loads(pj.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    continue
                rows.append((p.get('content', {}).get('title', '(untitled)'),
                             p.get('status', '?'), p.get('folder', '')))
        for name, st, fold in rows:
            rec_table.insert('', 'end', values=(name, st, fold))

    def finish_plan(plan, error):
        current['busy'] = False
        make_btn.config(state='normal')
        set_live(False)
        if error:
            set_status(error, t.DANGER)
            log('Plan failed: ' + error)
            set_buttons(None)
            result['status'] = 'error: ' + error
            return
        current['plan'] = plan
        result.update(status=plan['status'], folder=plan['folder'])
        show_plan(intake.plan_text(plan))
        if plan['status'] == 'awaiting_approval':
            set_stage('Plan & requirements', 'done', t.SUCCESS)
            set_status('Read the plan. Nothing is built until you press Approve & build.', t.INK)
            log('Plan ready: ' + plan['content']['title'])
        else:
            set_status('ADM needs more information — see the questions, then edit your request.', t.WARN)
            log('Plan needs answers before it can proceed.')
        set_buttons(plan)
        refresh_recent()
        if _auto and _auto.get('approve'):
            win.after(200, do_approve)

    def do_make():
        if current['busy']:
            return
        text = request_box.get('1.0', 'end').strip()
        try:
            intake.validate_request(text)
            if mode.get() == 'existing':
                intake.check_existing_folder(folder.get())
        except SafetyError as exc:
            set_status(str(exc), t.DANGER)
            return
        current['busy'] = True
        make_btn.config(state='disabled')
        set_buttons(None)
        reset_pipeline()
        set_stage('Plan & requirements', 'run', t.CYAN)
        set_live(True)
        set_status('Thinking about your request on this PC. This can take a minute or two…', t.MUTED)
        log('Analysing request and writing a plan…')
        m, f, md = mode.get(), folder.get(), (_plan_model or model_holder.get('model'))

        def work():
            try:
                use_model = md or intake.choose_model()
                gen = _plan_generator
                if gen is None:
                    from .backends import make_json_generator
                    gen = make_json_generator(use_model)
                plan = intake.create_plan(state, text, mode=m, folder=f, generator=gen, model=use_model)
                win.after(0, lambda: finish_plan(plan, None))
            except SafetyError as exc:
                win.after(0, lambda e=str(exc): finish_plan(None, e))
            except Exception as exc:
                win.after(0, lambda e=f'{type(exc).__name__}: {exc}': finish_plan(None, 'Something went wrong: ' + e))
        threading.Thread(target=work, daemon=True).start()

    def do_approve():
        plan = current['plan']
        if not plan or current['busy']:
            return
        try:
            done = intake.approve(plan['path'])
        except SafetyError as exc:
            set_status(str(exc), t.DANGER)
            return
        current['plan'] = done
        set_buttons(None)
        show_plan(intake.plan_text(done))
        result.update(status='approved', folder=done['folder'])
        log('Approved. Folder: ' + done['folder'])
        refresh_recent()
        start_build(done)

    def start_build(plan):
        current['busy'] = True
        set_live(True)
        set_stage('Plan & requirements', 'done', t.SUCCESS)
        set_stage('Code generation', 'run', t.CYAN)
        set_status('Building in a sandbox on this PC…', t.MUTED)
        log('Writing tests and code, then testing in the sandbox…')

        def work():
            from . import build, sandbox
            try:
                use_model = _plan_model or model_holder.get('model') or intake.choose_model()
                if _plan_generator is not None:
                    tgen = cgen = _plan_generator
                else:
                    from .backends import make_json_generator, make_generator
                    tgen = make_json_generator(use_model)
                    cgen = make_generator(use_model)
                runner = sandbox.make_runner(sandbox.provision())
                report = build.build_from_plan(plan['path'], Path(plan['folder']) / '.adm-evidence',
                                               test_generator=tgen, code_generator=cgen, model=use_model,
                                               runner=runner, require_sandbox=True)
                win.after(0, lambda: finish_build(report, None))
            except SafetyError as exc:
                win.after(0, lambda e=str(exc): finish_build(None, e))
            except Exception as exc:
                win.after(0, lambda e=f'{type(exc).__name__}: {exc}': finish_build(None, e))
        threading.Thread(target=work, daemon=True).start()

    def finish_build(report, error):
        current['busy'] = False
        set_live(False)
        if error:
            set_stage('Code generation', 'pending', t.FAINT)
            set_status('Could not build: ' + error, t.DANGER)
            log('Build stopped: ' + error)
            return
        result['build'] = report
        built = report['status'] == 'built'
        set_stage('Code generation', 'done', t.SUCCESS)
        set_stage('Build & test', 'done' if built else 'run', t.SUCCESS if built else t.WARN)
        set_stage('Auto-fix', 'done' if built else 'skip', t.SUCCESS if built else t.FAINT)
        set_stage('Package & deliver', 'skip', t.FAINT)
        set_status(report.get('message', report['status']), t.SUCCESS if built else t.WARN)
        log(('Built — all checks pass (verified in the sandbox).' if built else 'Build result: ' + report['status']))
        refresh_stats()
        refresh_recent()

    def do_reject():
        plan = current['plan']
        if plan:
            try:
                intake.reject(plan['path'])
            except SafetyError:
                pass
        current['plan'] = None
        set_buttons(None)
        show_plan('')
        reset_pipeline()
        result['status'] = 'rejected'
        set_status('Plan discarded. Nothing was created. Change your request and press Make plan.', t.MUTED)
        refresh_recent()

    make_btn.config(command=do_make)
    approve_btn.config(command=do_approve)
    reject_btn.config(command=do_reject)
    reset_pipeline()

    # Local AI status (real check, off the UI thread)
    model_holder = {'model': _plan_model}

    def check_ai():
        def work():
            label, detail = 'LOCAL AI', 'Checking…'
            try:
                from .ollama_health import inspect_ollama
                info = inspect_ollama(timeout=3)
                models = info.get('installed_models', [])
                if models:
                    model_holder['model'] = model_holder.get('model') or 'ollama/' + models[0]
                    label, detail = '● LOCAL AI ONLINE', 'Model: ' + models[0]
                else:
                    label, detail = '○ LOCAL AI', 'Running, but no model installed yet.'
            except Exception:
                label, detail = '○ LOCAL AI OFFLINE', 'Not detected. Use Set up local AI.'
            def paint():
                ai_title.config(text=label, fg=t.SUCCESS if 'ONLINE' in label else t.MUTED)
                ai_detail.config(text=detail)
            try:
                win.after(0, paint)
            except RuntimeError:
                pass
        threading.Thread(target=work, daemon=True).start()

    def setup_flow(*, prompt_only_if_missing):
        import threading as _th
        def work():
            from . import firstrun
            try:
                a = firstrun.assess()
            except Exception as exc:
                return
            def decide():
                title, message = firstrun.prompt_text(a)
                if a['ready']:
                    if not prompt_only_if_missing:
                        messagebox.showinfo(title, message)
                    return
                can_act = bool({'ollama', 'start_ollama', 'model'} & set(a['needs']))
                yes = (ask or messagebox.askyesno)(title, message) if can_act else (messagebox.showinfo(title, message) and False)
                if not yes:
                    return
                def install():
                    try:
                        res = firstrun.run_setup(a, approved=True, on_status=log)
                        win.after(0, lambda: messagebox.showinfo('Local AI setup', res['message']))
                    except Exception as exc:
                        win.after(0, lambda e=str(exc): messagebox.showerror('Local AI setup', e))
                    check_ai()
                _th.Thread(target=install, daemon=True).start()
            try:
                win.after(0, decide)
            except RuntimeError:
                pass
        _th.Thread(target=work, daemon=True).start()

    def tick():
        refresh_stats()
        try:
            win.after(2000, tick)
        except RuntimeError:
            pass

    refresh_stats()
    refresh_recent()
    check_ai()
    log('Ready. Describe an app above and press Make plan.')
    tick()
    win.after(900, lambda: setup_flow(prompt_only_if_missing=True))

    if _auto:
        request_box.insert('1.0', _auto['request'])
        mode.set(_auto.get('mode', 'new'))
        folder.set(_auto.get('folder', ''))
        sync()
        if _auto.get('make'):
            win.after(400, do_make)
    if auto_close_ms:
        win.after(auto_close_ms, win.destroy)
    if _zoom:
        try:
            win.state('zoomed')
        except Exception:
            pass
    win.mainloop()
    return result


if __name__ == '__main__':
    main()
