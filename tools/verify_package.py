"""Windows CI: package a tiny generated project into a one-file EXE and run it. Proves the whole
chain (entry generation -> PyInstaller -> runnable EXE). Exits non-zero on any failure."""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm import package

proj = Path(tempfile.mkdtemp(prefix='pkgcheck_'))
(proj / 'app.py').write_text('def add(a, b):\n    return a + b\n\ndef per_person(total, people):\n    return total / people\n')
plan = {'content': {'title': 'Adder Demo'}}

report = package.package_project(proj, proj / 'dist', plan=plan, python=sys.executable, timeout=1800)
print('PACKAGE STATUS:', report['status'], '->', report.get('exe'))
if report['status'] != 'packaged':
    print(report.get('output_tail', '')[-1800:])
    raise SystemExit(1)

exe = report['exe']
run = subprocess.run([exe, 'add', '2', '3'], capture_output=True, text=True, timeout=180)
print('EXE `add 2 3` ->', repr(run.stdout.strip()), 'rc', run.returncode)
help_run = subprocess.run([exe, '--help'], capture_output=True, text=True, timeout=180)
ok = run.returncode == 0 and '5' in run.stdout and 'add' in help_run.stdout and 'per_person' in help_run.stdout
print('PACKAGED EXE RUNS:', 'PASSED' if ok else 'FAILED')
raise SystemExit(0 if ok else 1)
