"""Ensure the frozen entrypoint propagates smoke-test failures to Windows CI."""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from adm import desktop_entry


class DesktopEntrypointExitTests(unittest.TestCase):
    def test_smoke_failure_returns_nonzero(self):
        with patch('adm.selftest.write_smoke_report', return_value={'passed': False}):
            self.assertEqual(desktop_entry.main(['--adm-self-test', 'unused.json']), 1)

    def test_smoke_success_returns_zero(self):
        with patch('adm.selftest.write_smoke_report', return_value={'passed': True}):
            self.assertEqual(desktop_entry.main(['--adm-self-test', 'unused.json']), 0)

    def test_real_script_propagates_invalid_arguments(self):
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run([sys.executable, '-m', 'adm.desktop_entry', '--invalid'],
                                   cwd=root, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('Unknown desktop arguments', completed.stderr)

    def test_real_script_smoke_produces_success_exit(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / 'report.json'
            root = Path(__file__).resolve().parents[1]
            completed = subprocess.run([sys.executable, '-m', 'adm.desktop_entry', '--adm-self-test', str(report)],
                                       cwd=root, capture_output=True, text=True, timeout=20)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(report.is_file())


if __name__ == '__main__':
    unittest.main()
