"""Windows only: open the ADM dashboard (maximized), grab the screen, print it as base64.
Driven by a FAKE local model so the plan and pipeline populate; no real AI runs."""
import base64, io, sys, threading, time, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import ImageGrab

which = sys.argv[1] if len(sys.argv) > 1 else 'dashboard'
delay = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0

PLAN = {'title': 'Tip calculator',
        'summary': 'A small window where you type a bill and a tip percent, and it shows the total and what each person owes when the bill is split.',
        'features': ['Type in the bill amount', 'Pick a tip percent (10, 15, 20 or your own)',
                     'Say how many people are splitting it', 'Show the total and each person\'s share'],
        'tests': ['When the bill is 100 and the tip is 20 percent, the total is 120',
                  'When 120 is split between 4 people, each person pays 30',
                  'When the tip is 0 percent, the total equals the bill'],
        'needs_internet': False, 'questions': []}


def fake(model, prompt, timeout=300):
    return PLAN


def grab():
    time.sleep(delay)
    img = ImageGrab.grab()
    buf = io.BytesIO()
    img.save(buf, 'PNG', optimize=True)
    data = base64.b64encode(buf.getvalue()).decode()
    print(f'PNGBEGIN {which} {img.size[0]}x{img.size[1]}', flush=True)
    for i in range(0, len(data), 200):
        print(data[i:i + 200], flush=True)
    print('PNGEND', flush=True)


threading.Thread(target=grab, daemon=True).start()
from adm import dashboard
auto = {'request': 'I want a small program where I type a bill and a tip percent and it tells me what everyone owes.',
        'mode': 'new', 'make': which != 'empty'}
dashboard.main(auto_close_ms=int((delay + 2) * 1000), ask=lambda t, m: False,
               _plan_generator=fake, _plan_model='ollama/fake', _auto=auto, _zoom=True)
