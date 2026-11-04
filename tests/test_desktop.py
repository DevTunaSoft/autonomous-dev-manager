import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from adm.desktop import status_summary, launch_supervisor
from adm.daemon import _atomic_json

class DesktopTests(unittest.TestCase):
    def test_missing_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(status_summary(tmp)['state'], 'unknown')
    def test_fresh_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            _atomic_json(Path(tmp)/'daemon-status.json', {'state':'running','heartbeat_at':100,'pid':7})
            self.assertEqual(status_summary(tmp, now=110)['state'], 'running')
    def test_stale_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            _atomic_json(Path(tmp)/'daemon-status.json', {'state':'running','heartbeat_at':100})
            self.assertEqual(status_summary(tmp, now=200)['state'], 'unresponsive')
    def test_future_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            _atomic_json(Path(tmp)/'daemon-status.json', {'state':'running','heartbeat_at':200})
            self.assertEqual(status_summary(tmp, now=100)['state'], 'unresponsive')
    def test_no_duplicate_when_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            import time
            _atomic_json(Path(tmp)/'daemon-status.json', {'state':'running','heartbeat_at':time.time()})
            with patch('adm.desktop.subprocess.Popen') as popen:
                self.assertFalse(launch_supervisor(tmp)['started'])
                popen.assert_not_called()
    def test_launch_uses_real_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('adm.desktop.subprocess.Popen') as popen:
                popen.return_value.pid = 123
                result=launch_supervisor(tmp, executable='python-test', frozen=False)
                self.assertTrue(result['started'])
                args, kwargs=popen.call_args
                self.assertEqual(args[0][:3], ['python-test','-m','adm.daemon'])
                self.assertEqual(kwargs['cwd'],str(Path(tmp).resolve()))

if __name__ == '__main__': unittest.main()

class BuildPlanTests(unittest.TestCase):
    def test_windows_gui_build_plan(self):
        from adm.release import windows_desktop_build_plan
        root = Path(__file__).resolve().parent.parent
        cmd = windows_desktop_build_plan(root, python_executable='py')
        self.assertIn('--windowed', cmd)
        self.assertIn('ADM-Desktop', cmd)
        self.assertTrue(cmd[-1].endswith('desktop_entry.py'))
