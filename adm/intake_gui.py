"""The 'New request' window: describe -> Make plan -> read -> Approve. Thin layer over adm.intake."""
from __future__ import annotations
import threading
from pathlib import Path
from . import intake
from .engine import SafetyError

WELCOME = ("Describe the app or change you want, in your own words.\n"
           "Example: A small program where I type a bill and a tip percent and it tells me what everyone owes.")


def open_request_window(parent, state, *, generator=None, model=None, auto=None, auto_close_ms=None):
    """`generator`/`model` override the real local model (used by the Windows window check only).
    `auto` = {'request','mode','folder','approve'} drives the window for that check."""
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    win = tk.Toplevel(parent) if parent is not None else tk.Tk()
    win.title('ADM — New request')
    win.geometry('780x640'); win.minsize(640, 480)
    tk.Label(win, text=WELCOME, wraplength=740, justify='left').pack(anchor='w', padx=16, pady=(14, 4))
    box = tk.Text(win, height=7, wrap='word')
    box.pack(fill='x', padx=16)
    mode = tk.StringVar(value='new')
    row = tk.Frame(win); row.pack(fill='x', padx=16, pady=6)
    folder = tk.StringVar()
    entry = ttk.Entry(row, textvariable=folder, width=60, state='disabled')
    browse = ttk.Button(row, text='Browse...', state='disabled',
                        command=lambda: folder.set(filedialog.askdirectory(title='Choose your project folder') or folder.get()))
    def sync():
        on = 'normal' if mode.get() == 'existing' else 'disabled'
        entry.config(state=on); browse.config(state=on)
    tk.Radiobutton(row, text='New project', variable=mode, value='new', command=sync).pack(side='left')
    tk.Radiobutton(row, text='Existing folder:', variable=mode, value='existing', command=sync).pack(side='left', padx=(12, 4))
    entry.pack(side='left'); browse.pack(side='left', padx=4)
    status = tk.StringVar(value='Nothing has been created or run yet.')
    buttons = tk.Frame(win); buttons.pack(pady=6)
    make_btn = ttk.Button(buttons, text='Make plan')
    approve_btn = ttk.Button(buttons, text='Approve this plan', state='disabled')
    reject_btn = ttk.Button(buttons, text='Not this — start over', state='disabled')
    for b in (make_btn, approve_btn, reject_btn):
        b.pack(side='left', padx=6)
    tk.Label(win, textvariable=status, wraplength=740, justify='left', fg='#333').pack(anchor='w', padx=16)
    out = tk.Text(win, height=12, wrap='word', state='disabled', bg='#f6f6f6')
    out.pack(fill='both', expand=True, padx=16, pady=8)
    current = {'plan': None, 'busy': False}
    result = {'status': 'no plan', 'plan_text': '', 'folder': ''}

    def show(text):
        out.config(state='normal'); out.delete('1.0', 'end'); out.insert('1.0', text); out.config(state='disabled')

    def set_buttons(plan):
        ok = plan is not None and plan['status'] == 'awaiting_approval'
        approve_btn.config(state='normal' if ok else 'disabled')
        reject_btn.config(state='normal' if plan is not None and plan['status'] in ('awaiting_approval', 'needs_answers') else 'disabled')

    def finish_plan(plan, error):
        current['busy'] = False
        make_btn.config(state='normal')
        if error:
            status.set(error); show(''); set_buttons(None); result['status'] = 'error: ' + error
            return
        current['plan'] = plan
        result.update(status=plan['status'], plan_text=intake.plan_text(plan), folder=plan['folder'])
        show(result['plan_text'])
        status.set('Read the plan. Nothing is created until you press Approve.' if plan['status'] == 'awaiting_approval'
                   else 'ADM needs a bit more information first (see the questions below).')
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
            status.set(str(exc)); return
        current['busy'] = True; make_btn.config(state='disabled'); set_buttons(None)
        status.set('Thinking about your request on this PC. This can take a minute or two...')
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
            status.set(str(exc)); return
        current['plan'] = done; set_buttons(None)
        show(intake.plan_text(done))
        result.update(status='approved', folder=done['folder'])
        status.set('Approved and saved. The step that writes the code is not built yet, so nothing will be '
                   'written or run. Your folder: ' + done['folder'])

    def do_reject():
        plan = current['plan']
        if plan:
            try:
                intake.reject(plan['path'])
            except SafetyError as exc:
                status.set(str(exc)); return
        current['plan'] = None; set_buttons(None); show(''); result['status'] = 'rejected'
        status.set('Plan discarded. Nothing was created. Change your request and press Make plan.')

    make_btn.config(command=do_make); approve_btn.config(command=do_approve); reject_btn.config(command=do_reject)
    if auto:
        box.insert('1.0', auto['request']); mode.set(auto.get('mode', 'new')); folder.set(auto.get('folder', '')); sync()
        win.after(300, do_make)
    if auto_close_ms:
        win.after(auto_close_ms, win.destroy)
    return win, result
