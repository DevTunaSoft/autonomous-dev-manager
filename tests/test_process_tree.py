"""ADM-037 process-tree timeout tests (trusted disposable test programs only)."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from adm.engine import run_checked


class ProcessTreeTests(unittest.TestCase):
    def test_success_output(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_checked([sys.executable, '-c', 'print("hello")'], directory, directory)
            self.assertEqual(result['exit_code'], 0)
            self.assertIn('hello', result['output'])

    def test_timeout_kills_descendant(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'child-finished'
            child = 'import time,pathlib;time.sleep(1.5);pathlib.Path(%r).write_text("escaped")' % str(marker)
            parent = 'import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",%r]);time.sleep(10)' % child
            result = run_checked([sys.executable, '-c', parent], directory, directory, timeout=0.3)
            self.assertEqual(result['exit_code'], 124)
            time.sleep(1.8)
            self.assertFalse(marker.exists(), 'Child survived timed-out parent')

    def test_nonexistent_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_checked(['adm-nonexistent-executable-037'], directory, directory)
            self.assertEqual(result['exit_code'], 127)

if __name__ == '__main__':
    unittest.main()
