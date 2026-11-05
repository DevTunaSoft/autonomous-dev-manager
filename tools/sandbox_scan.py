"""Run AS the sandbox account: list directories where it can create a file (depth <= 3 from C:\\)."""
import os, sys, uuid
roots = [r'C:\\']
writable, seen = [], 0
def can_write(d):
    p = os.path.join(d, 'adm_' + uuid.uuid4().hex + '.tmp')
    try:
        with open(p, 'w') as f: f.write('x')
        os.remove(p); return True
    except OSError:
        return False
def walk(d, depth):
    global seen
    seen += 1
    if can_write(d): writable.append(d)
    if depth == 0: return
    try:
        for e in os.scandir(d):
            if e.is_dir(follow_symlinks=False):
                walk(e.path, depth - 1)
    except OSError:
        pass
walk(r'C:\\', 3)
print('RAN scanned=%d' % seen)
for d in writable[:60]: print('WRITABLE', d)
