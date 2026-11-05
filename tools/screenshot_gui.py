"""Windows only: open one ADM window, grab the screen, print it as base64 between markers (read from the CI log)."""
import base64, io, sys, threading, time, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import ImageGrab

which, delay = sys.argv[1], float(sys.argv[2])

def grab():
    time.sleep(delay)
    img = ImageGrab.grab()
    buf = io.BytesIO(); img.save(buf, 'PNG', optimize=True)
    data = base64.b64encode(buf.getvalue()).decode()
    print(f'PNGBEGIN {which} {img.size[0]}x{img.size[1]}', flush=True)
    for i in range(0, len(data), 200): print(data[i:i+200], flush=True)
    print('PNGEND', flush=True)

PLAN = {'title': 'Tip calculator', 'summary': 'A small window where you type a bill and a tip percent, and it shows the total and what each person owes when the bill is split.',
        'features': ['Type in the bill amount', 'Pick a tip percent (10, 15, 20 or your own)', 'Say how many people are splitting it', 'Show the total and each person\'s share'],
        'tests': ['When the bill is 100 and the tip is 20 percent, the total is 120',
                  'When 120 is split between 4 people, each person pays 30',
                  'When the tip is 0 percent, the total equals the bill',
                  'When the number of people is 0, it shows a clear message instead of crashing'],
        'needs_internet': False, 'questions': []}
def fake(model, prompt, timeout): return PLAN

threading.Thread(target=grab, daemon=True).start()
if which == 'main':
    from adm import desktop
    desktop.main(auto_close_ms=int((delay + 2) * 1000), ask=lambda t, m: False)
else:
    from adm.intake_gui import open_request_window
    state = Path(tempfile.mkdtemp(prefix='adm-shot-'))
    auto = {'request': 'I want a small program where I type a bill and a tip percent and it tells me what everyone owes.',
            'mode': 'new', 'approve': which == 'approved'}
    win, result = open_request_window(None, state, generator=fake, model='ollama/fake', auto=auto, auto_close_ms=int((delay + 2) * 1000))
    win.mainloop()
