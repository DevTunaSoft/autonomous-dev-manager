import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from adm.desktop import launch_supervisor, recent_jobs
from adm.desktop_entry import main

class SingleExecutableTests(unittest.TestCase):
    def test_frozen_launch_uses_embedded_supervisor(self):
        with tempfile.TemporaryDirectory() as temp, patch('adm.desktop.subprocess.Popen') as popen:
            popen.return_value.pid = 99
            result = launch_supervisor(temp, executable='ADM-Desktop.exe', frozen=True)
            self.assertEqual(result['pid'], 99)
            self.assertEqual(popen.call_args.args[0][:2], ['ADM-Desktop.exe', '--adm-supervisor'])
    def test_entry_routes_supervisor_arguments(self):
        with patch('adm.daemon.main', return_value=12) as daemon:
            self.assertEqual(main(['--adm-supervisor', '--state', 'abc']), 12)
            daemon.assert_called_once_with(['--state', 'abc'])
    def test_entry_routes_gui(self):
        with patch('adm.desktop.main', return_value=7) as gui:
            self.assertEqual(main([]), 7)
            gui.assert_called_once_with()
    def test_unknown_args_rejected(self):
        with self.assertRaises(SystemExit):
            main(['--unexpected'])
    def test_missing_db_does_not_create(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(recent_jobs(temp), [])
            self.assertFalse((Path(temp) / 'jobs.sqlite').exists())
    def test_read_only_jobs(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'jobs.sqlite'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE jobs(id INTEGER, label TEXT, state TEXT, attempts INTEGER, exit_code INTEGER)')
                db.execute("INSERT INTO jobs VALUES(1,'build','pending',0,NULL)")
                db.execute("INSERT INTO jobs VALUES(2,'test','passed',1,0)")
            self.assertEqual([j['id'] for j in recent_jobs(temp, limit=1)], [2])
            self.assertEqual(recent_jobs(temp)[1]['label'], 'build')
    def test_limit_validation(self):
        for value in (0, 101, True, '5'):
            with self.assertRaises(ValueError):
                recent_jobs('.', limit=value)

if __name__ == '__main__': unittest.main()
