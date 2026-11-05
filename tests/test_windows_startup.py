import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from adm.windows_startup import startup_command, windows_task_command, install
from adm.daemon import request_stop, serve, read_status

class StartupTests(unittest.TestCase):
    def test_windows_command_is_argv_not_shell(self):
        with tempfile.TemporaryDirectory(prefix='adm spaces ') as tmp:
            cmd = windows_task_command(tmp)
            self.assertEqual(cmd[0], 'schtasks.exe')
            self.assertIn('ONLOGON', cmd)
            self.assertIn('LIMITED', cmd)
            self.assertIn(str(Path(tmp).resolve()), cmd[-3])
    def test_frozen_startup_uses_supervisor_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sys, 'frozen', True, create=True):
                cmd = startup_command(tmp)
            self.assertEqual(cmd[1:3], ['--adm-supervisor', '--state'])
            self.assertEqual(cmd[3], str(Path(tmp).resolve()))
    def test_source_startup_uses_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sys, 'frozen', False, create=True):
                cmd = startup_command(tmp)
            self.assertEqual(cmd[1:3], ['-m', 'adm.daemon'])
    def test_no_automatic_install(self):
        from adm.engine import SafetyError
        with self.assertRaises((PermissionError, SafetyError)):
            install('ignored', approve=False)
    def test_missing_python_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            startup_command('.', python_executable='/unlikely/nonexistent/python.exe')
    def test_existing_stop_request_is_not_discarded(self):
        with tempfile.TemporaryDirectory() as tmp:
            request_stop(tmp)
            self.assertEqual(serve(tmp, poll_interval=.05, max_cycles=3), 0)
            self.assertEqual(read_status(tmp)['state'], 'stopped')

if __name__ == '__main__': unittest.main()
