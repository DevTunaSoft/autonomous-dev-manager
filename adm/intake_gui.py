"""The 'New request' window: describe -> Make plan -> read -> Approve. Thin layer over adm.intake."""
from __future__ import annotations
import threading
from pathlib import Path
from . import intake
from .engine import SafetyError

WELCOME = 'Describe the app or change you want, in your own words.'
EXAMPLE = 'For example: "A small program where I type a bill and a tip percent and it tells me what everyone owes."'


def open_request_window(parent, state, *, generator=None, model=None, auto=None, auto_close_ms=None):
    """`generator`/`model` override the real local model (used by the Windows window check only).
    `auto` = {'request','mode','folder','approve'} drives the window for that check."""
    import tkinter as tk
    from tkinter import ttk, filedialog
    from . import theme
    win = tk.Toplevel(parent) if parent is not None else tk.Tk()
    win.title('ADM — New request')
    win.geometry('820x680')
    win.minsize(680, 600)
    theme.apply(win)

    theme.header(win, 'New request', 'Nothing is created or run until you read the plan and press Approve.').pack(fill='x')
    body = ttk.Frame(win, style='TFrame')
    body.pack(fill='both', expand=True, padx=24, pady=(16, 18))

    ttk.Label(body, text=WELCOME, style='Heading.TLabel').pack(anchor='w')
    ttk.Label(body, text=EXAMPLE, style='Muted.TLabel', wraplength=760, justify='left').pack(anchor='w', pady=(2, 8))

    box_frame, box = theme.entry_text(body, height=5)
    box_frame.pack(fill='x')

    mode = tk.StringVar(value='new')
    row = ttk.Frame(body, style='TFrame')
    row.pack(fill='x', pady=(12, 4))
    folder = tk.StringVar()
    entry = ttk.Entry(row, textvariable=folder, width=52, state='disabled')
    browse = ttk.Button(row, text='Browse…', style='Secondary.TButton', state='disabled',
                        command=lambda: folder.set(filedialog.askdirectory(title='Choose your project folder') or folder.get()))

    def sync():
        on = 'normal' if mode.get() == 'existing' else 'disabled'
        entry.config(state=on)
        browse.config(state=on)
    ttk.Radiobutton(row, text='New project', variable=mode, value='new', command=sync).pack(side='left')
    ttk.Radiobutton(row, text='Existing folder:', variable=mode, value='existing', command=sync).pack(side='left', padx=(16, 8))
    entry.pack(side='left', fill='x', expand=True)
    browse.pack(side='left', padx=(8, 0))

    actions = ttk.Frame(body, style='TFrame')
    actions.pack(fill='x', pady=(14, 6))
    make_btn = ttk.Button(actions, text='Make plan', style='Primary.TButton')
    approve_btn = ttk.Button(actions, text='✓  Approve this plan', style='Primary.TButton', state='disabled')
    reject_btn = ttk.Button(actions, text='Not this — start over', style='Danger.TButton', state='disabled')
    make_btn.pack(side='left')
    approve_btn.pack(side='left', padx=8)
    reject_btn.pack(side='left')

    status = tk.StringVar(value='Nothing has been created or run yet.')
    status_label = ttk.Label(body, textvariable=status, style='Muted.TLabel', wraplength=760, justify='left')
    status_label.pack(anchor='w', pady=(6, 6))

    panel, out = theme.document(body, height=12)
    panel.pack(fill='both', expand=True)

    current = {'plan': None, 'busy': False}
    result = {'status': 'no plan', 'plan_text': '', 'folder': ''}

    def show(text):
        out.config(state='normal')
        out.delete('1.0', 'end')
        out.insert('1.0', text)
        out.config(state='disabled')

    def set_status(text, kind='muted'):
        status.set(text)
        status_label.configure(foreground={'muted': theme.MUTED, 'ok': theme.SUCCESS,
                                            'warn': theme.DANGER}.get(kind, theme.MUTED))

    def set_buttons(plan):
        ok = plan is not None and plan['status'] == 'awaiting_approval'
        approve_btn.config(state='normal' if ok else 'disabled')
        reject_btn.config(state='normal' if plan is not None and plan['status'] in ('awaiting_approval', 'needs_answers') else 'disabled')

    def finish_plan(plan, error):
        current['busy'] = False
        make_btn.config(state='normal')
        if error:
            set_status(error, 'warn')
            show('')
            set_buttons(None)
            result['status'] = 'error: ' + error
            return
        current['plan'] = plan
        result.update(status=plan['status'], plan_text=intake.plan_text(plan), folder=plan['folder'])
        show(result['plan_text'])
        if plan['status'] == 'awaiting_approval':
            set_status('Read the plan below. Nothing is created until you press Approve.', 'muted')
        else:
            set_status('ADM needs a bit more information first — see the questions below, then edit your request.', 'warn')
        set_buttons(plan)
        if auto and auto.get('approve') and plan['status'] == 'awaiting_approval':
            win.after(200, do_approve)

    def do_make():
        if current['busy']:
            return
        text = box.get('1.0', 'end').strip()
        try:
            intake.validate_request(text)
            if mode.get() == 'existing':
                intake.check_existing_folder(folder.get())
        except SafetyError as exc:
            set_status(str(exc), 'warn')
            return
        current['busy'] = True
        make_btn.config(state='disabled')
        set_buttons(None)
        set_status('Thinking about your request on this PC. This can take a minute or two…', 'muted')
        m, f, md = mode.get(), folder.get(), model

        def work():
            try:
                use_model = md or intake.choose_model()
                use_gen = generator
                if use_gen is None:
                    from .backends import make_json_generator
                    use_gen = make_json_generator(use_model)
                plan = intake.create_plan(state, text, mode=m, folder=f, generator=use_gen, model=use_model)
                win.after(0, lambda: finish_plan(plan, None))
            except SafetyError as exc:
                msg = str(exc)
                win.after(0, lambda: finish_plan(None, msg))
            except Exception as exc:                       # never leave the window stuck on 'Thinking'
                msg = f'Something went wrong while planning: {type(exc).__name__}: {exc}'
                win.after(0, lambda: finish_plan(None, msg))
        threading.Thread(target=work, daemon=True).start()

    def do_approve():
        plan = current['plan']
        if not plan:
            return
        try:
            done = intake.approve(plan['path'])
        except SafetyError as exc:
            set_status(str(exc), 'warn')
            return
        current['plan'] = done
        set_buttons(None)
        show(intake.plan_text(done))
        result.update(status='approved', folder=done['folder'])
        set_status('Approved and saved. The step that writes the code is not built yet, so nothing will be '
                   'written or run. Your folder: ' + done['folder'], 'ok')

    def do_reject():
        plan = current['plan']
        if plan:
            try:
                intake.reject(plan['path'])
            except SafetyError as exc:
                set_status(str(exc), 'warn')
                return
        current['plan'] = None
        set_buttons(None)
        show('')
        result['status'] = 'rejected'
        set_status('Plan discarded. Nothing was created. Change your request and press Make plan.', 'muted')

    make_btn.config(command=do_make)
    approve_btn.config(command=do_approve)
    reject_btn.config(command=do_reject)
    box.focus_set()
    if auto:
        box.insert('1.0', auto['request'])
        mode.set(auto.get('mode', 'new'))
        folder.set(auto.get('folder', ''))
        sync()
        win.after(300, do_make)
    if auto_close_ms:
        win.after(auto_close_ms, win.destroy)
    return win, result
