"""Run AS the sandbox account: can it create a file in each directory named on the command line?"""
import os, sys, uuid
def can_write(d):
    p = os.path.join(d, 'adm_' + uuid.uuid4().hex + '.tmp')
    try:
        with open(p, 'w') as f: f.write('x')
        os.remove(p); return True
    except OSError:
        return False
print('RAN')
for d in sys.argv[1:]:
    print(('WRITABLE ' if can_write(d) else 'refused  ') + d)
