import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from adm import package
from adm.engine import SafetyError

PLAN = {'content': {'title': 'Tip Calculator'}}


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'proj'
        self.root.mkdir()
        (self.root / 'app.py').write_text('def add(a, b):\n    return a + b\n\n'
                                          'def greet(name):\n    return "hi " + name\n')

    def test_exe_name_is_sanitised(self):
        self.assertEqual(package.exe_name('Tip Calculator!!'), 'tip-calculator')
        self.assertEqual(package.exe_name('***'), 'app')
        self.assertEqual(package.exe_name('模型'), 'app')

    def test_generated_entry_is_valid_and_runs_the_app(self):
        entry = package.write_entry(self.root, PLAN)
        self.assertTrue(entry.is_file())
        compile(entry.read_text(), 'main.py', 'exec')               # valid Python
        # the generated CLI actually runs the app's functions
        r = subprocess.run([sys.executable, str(entry), 'add', '2', '3'],
                           cwd=self.root, capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(r.returncode, 0)
        self.assertIn('5', r.stdout)
        r = subprocess.run([sys.executable, str(entry), '--help'], cwd=self.root,
                           capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertIn('add', r.stdout)
        self.assertIn('greet', r.stdout)
        # an unknown command exits non-zero without crashing
        r = subprocess.run([sys.executable, str(entry), 'nope'], cwd=self.root,
                           capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(r.returncode, 2)

    def test_write_entry_does_not_overwrite_existing_main(self):
        (self.root / 'main.py').write_text('# my own entry\n')
        package.write_entry(self.root, PLAN)
        self.assertEqual((self.root / 'main.py').read_text(), '# my own entry\n')

    def test_package_requires_app_and_a_packager(self):
        empty = Path(self.tmp.name) / 'empty'
        empty.mkdir()
        with self.assertRaises(SafetyError):
            package.package_project(empty, empty / 'dist', plan=PLAN)        # no app.py
        # no packager python available -> clean message
        with self.assertRaises(SafetyError):
            package.package_project(self.root, self.root / 'dist', plan=PLAN,
                                    python=None if package.find_packager_python([]) is None else 'x')

    def test_package_command_is_onefile_console(self):
        cmd = package.package_command('py', Path('main.py'), 'tip', Path('d'), Path('b'))
        self.assertIn('--onefile', cmd)
        self.assertIn('--console', cmd)
        self.assertIn('tip', cmd)

    def test_find_packager_python_detects_pyinstaller(self):
        # this interpreter may or may not have PyInstaller; the call must not raise and return str|None
        result = package.find_packager_python([sys.executable])
        self.assertIn(result, (sys.executable, None))

    def test_hostile_titles_still_generate_valid_python(self):
        # Windows paths, trailing backslashes, quotes, null bytes, newlines,
        # and the template's own tokens must never break the generated entry.
        hostile = [
            r'C:\Users\x', 'ends with backslash\\', 'quote"inside',
            'triple"""quote', 'new\nline\ttab', '\x00null\x01', "'single'",
            '__ADM_EXE__', '__ADM_TITLE__', 'café ☕', 'A' * 300, '',
        ]
        for title in hostile:
            root = Path(self.tmp.name) / ('h' + str(abs(hash(title)) % 10**8))
            root.mkdir()
            (root / 'app.py').write_text('def add(a, b):\n    return a + b\n')
            entry = package.write_entry(root, {'content': {'title': title}})
            src = entry.read_text(encoding='utf-8')
            compile(src, 'main.py', 'exec')         # must be valid Python
            r = subprocess.run([sys.executable, str(entry), 'add', '2', '3'],
                               cwd=root, capture_output=True, text=True, encoding='utf-8', timeout=30)
            self.assertEqual(r.returncode, 0, f'title={title!r}: {r.stderr}')
            self.assertIn('5', r.stdout)

    def test_malformed_plans_do_not_crash(self):
        # A plan of any shape must degrade to a safe default title, never raise.
        for plan in (None, [], 'string', 42, {}, {'content': None},
                     {'content': []}, {'content': 'x'}, {'content': {}},
                     {'content': {'title': None}}, {'content': {'title': 123}}):
            self.assertIsInstance(package.plan_title(plan), str)
            self.assertTrue(package.plan_title(plan))                # non-empty
            root = Path(self.tmp.name) / ('m' + str(abs(hash(repr(plan))) % 10**8))
            root.mkdir()
            (root / 'app.py').write_text('def add(a, b):\n    return a + b\n')
            entry = package.write_entry(root, plan)                  # must not raise
            compile(entry.read_text(encoding='utf-8'), 'main.py', 'exec')


if __name__ == '__main__':
    unittest.main()
