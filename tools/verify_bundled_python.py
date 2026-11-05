"""Prove the embeddable Python runtime can run a project's unittest discover (cwd import works)."""
import subprocess, tempfile
from pathlib import Path
py = (Path('pyembed') / 'python.exe').resolve()
proj = Path(tempfile.mkdtemp(prefix='embedcheck_'))
(proj / 'app.py').write_text('def add(a, b):\n    return a + b\n')
(proj / 'test_app.py').write_text('import unittest\nfrom app import add\n'
                                  'class T(unittest.TestCase):\n    def test(self):\n        self.assertEqual(add(2, 3), 5)\n')
r = subprocess.run([str(py), '-m', 'unittest', 'discover', '-s', '.', '-p', 'test_*.py', '-v'],
                   cwd=proj, capture_output=True, text=True, timeout=60)
print(r.stdout); print(r.stderr)
print('BUNDLED PYTHON DISCOVER:', 'PASSED' if r.returncode == 0 else 'FAILED', 'rc=%d' % r.returncode)
raise SystemExit(0 if r.returncode == 0 else 1)
