import json, sys, tempfile, unittest
from pathlib import Path
from adm.pyruntime import self_command, project_python, PythonNotFound, ENTRY_MODULES
from adm import desktop_entry
from adm.engine import make_broken_demo


class PyRuntimeTests(unittest.TestCase):
    def test_frozen_self_command_reenters_exe(self):
        cmd = self_command('adm.ollama_cli', ['--root', 'x'], frozen=True, executable='C:/ADM.exe')
        self.assertEqual(cmd, ['C:/ADM.exe', '--adm-module', 'adm.ollama_cli', '--root', 'x'])

    def test_source_self_command_uses_interpreter(self):
        cmd = self_command('adm.ollama_cli', ['--root', 'x'], frozen=False)
        self.assertEqual(cmd[0], sys.executable)
        self.assertIn('-c', cmd)

    def test_unapproved_module_refused(self):
        with self.assertRaises(ValueError):
            self_command('os', [], frozen=True)

    def test_frozen_uses_discovered_python_and_never_the_exe(self):
        self.assertEqual(project_python(frozen=True, candidates=['/no/such/python', sys.executable]),
                         str(Path(sys.executable)))

    def test_frozen_without_python_gives_friendly_error(self):
        with self.assertRaises(PythonNotFound) as ctx:
            project_python(frozen=True, candidates=['/no/such/python'])
        self.assertIn('Python 3.10', str(ctx.exception))

    def test_windowsapps_stub_is_never_executed(self):
        with tempfile.TemporaryDirectory() as t:
            stub = Path(t) / 'WindowsApps' / 'python.exe'
            stub.parent.mkdir()
            stub.write_text('')
            with self.assertRaises(PythonNotFound):
                project_python(frozen=True, candidates=[str(stub)])

    def test_entry_dispatch_runs_repair_cli_in_process(self):
        with tempfile.TemporaryDirectory() as t:
            proj = Path(t) / 'p'
            make_broken_demo(proj)
            (proj / 'calculator.py').write_text('def add(a, b):\n    return a + b\n', newline='')
            ev = Path(t) / 'ev'
            code = desktop_entry.main(['--adm-module', 'adm.ollama_cli', '--root', str(proj), '--evidence', str(ev)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads((ev / 'ollama-direct-report.json').read_text())['status'], 'baseline_passed')

    def test_entry_dispatch_rejects_unlisted_module(self):
        with self.assertRaises(SystemExit):
            desktop_entry.main(['--adm-module', 'os', 'x'])
        self.assertIn('adm.ollama_cli', ENTRY_MODULES)


if __name__ == '__main__':
    unittest.main()
