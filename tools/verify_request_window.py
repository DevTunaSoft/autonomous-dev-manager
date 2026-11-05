"""Windows check: open the REAL request window, make a plan with a FAKE model, approve it, verify the folder.
Not a test of any real AI. Exits nonzero unless the plan was approved and its folder exists."""
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.intake_gui import open_request_window

PLAN = {'title': 'Tip calculator', 'summary': 'A small window that works out a tip and splits a bill.',
        'features': ['Enter a bill', 'Pick a tip percent'], 'tests': ['When the bill is 100 and the tip is 20 percent, the total is 120'],
        'needs_internet': False, 'questions': []}

def fake(model, prompt, timeout):
    return PLAN
fake.adm_live_generator = False

state = Path(tempfile.mkdtemp(prefix='adm-state-'))
win, result = open_request_window(None, state, generator=fake, model='ollama/fake-for-window-check',
                                  auto={'request': 'I want a tip calculator app', 'mode': 'new', 'approve': True},
                                  auto_close_ms=20000)
def poll():
    if result['status'] in ('approved',) or result['status'].startswith('error'):
        win.after(500, win.destroy)
    else:
        win.after(200, poll)
win.after(500, poll)
win.mainloop()
print(json.dumps(result, indent=1))
print('----- TEXT THE USER SEES -----'); print(result['plan_text'])
ok = result['status'] == 'approved' and Path(result['folder']).is_dir()
print('REQUEST WINDOW CHECK:', 'PASSED' if ok else 'FAILED')
raise SystemExit(0 if ok else 1)
