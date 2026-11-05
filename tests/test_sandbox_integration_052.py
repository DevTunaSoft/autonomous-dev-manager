import json, subprocess, sys, tempfile, unittest
from pathlib import Path
from adm import sandbox
from adm.engine import make_broken_demo, run_checked, SafetyError
from adm.ollama_direct import direct_repair


def fix_patch_generator(root):
    def fake(model, prompt, timeout):
        return {'files': [{'path': 'calculator.py', 'content': 'def add(a,b):\n    return a+b\n'}]}
    return fake


class SandboxIntegrationTests(unittest.TestCase):
    def test_default_run_reports_no_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_broken_demo(Path(tmp) / 'p')
            report = direct_repair(root, Path(tmp) / 'e', generator=fix_patch_generator(root))
            self.assertEqual(report['isolation'], 'none')

    def test_sandbox_runner_is_recorded_and_used_for_every_test_run(self):
        calls = []
        def fake_sandbox(argv, cwd, root, timeout=90, output_limit=30000):
            calls.append(argv)
            return run_checked(argv, cwd, root, timeout=timeout)
        fake_sandbox.adm_isolation = 'sandbox'
        with tempfile.TemporaryDirectory() as tmp:
            root = make_broken_demo(Path(tmp) / 'p')
            report = direct_repair(root, Path(tmp) / 'e', generator=fix_patch_generator(root), runner=fake_sandbox)
            self.assertEqual(report['isolation'], 'sandbox')
            self.assertEqual(report['status'], 'verified_direct_repair')
            self.assertGreaterEqual(len(calls), 3)   # baseline, patched run, independent verification

    def test_cli_sandbox_flag_never_falls_back_to_unsandboxed(self):
        if sandbox.available():
            self.skipTest('Windows: the live check covers this')
        with tempfile.TemporaryDirectory() as tmp:
            root = make_broken_demo(Path(tmp) / 'p')
            r = subprocess.run([sys.executable, '-m', 'adm.ollama_cli', '--root', str(root),
                                '--evidence', str(Path(tmp) / 'e'), '--sandbox'],
                               capture_output=True, text=True, timeout=60)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('nothing was run', r.stderr)
            self.assertFalse((Path(tmp) / 'e' / 'ollama-direct-report.json').exists())

    def test_runner_rejects_other_working_directory(self):
        runner = sandbox.make_runner('pw')
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'sub').mkdir()
            with self.assertRaises(SafetyError):
                runner(['x'], Path(tmp) / 'sub', tmp)


if __name__ == '__main__':
    unittest.main()
