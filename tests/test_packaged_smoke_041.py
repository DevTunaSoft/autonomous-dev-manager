import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from adm.desktop_entry import main
from adm.selftest import smoke_report, write_smoke_report

class PackagedSmokeTests(unittest.TestCase):
    def test_real_offline_smoke(self):
        result = smoke_report()
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['checks']['sqlite_wal_and_schema'], 'passed')
    def test_atomic_json(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'report.json'
            report = write_smoke_report(path)
            self.assertEqual(json.loads(path.read_text())['passed'], report['passed'])
    def test_frozen_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'report.json'
            self.assertEqual(main(['--adm-self-test', str(path)]), 0)
            self.assertTrue(json.loads(path.read_text())['passed'])
    def test_failure_is_nonzero(self):
        with patch('adm.selftest.smoke_report', return_value={'passed': False, 'checks': {'x': 'failed'}}):
            with tempfile.TemporaryDirectory() as temp:
                self.assertEqual(main(['--adm-self-test', str(Path(temp)/'report.json')]), 1)
    def test_missing_parent_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                write_smoke_report(Path(temp)/'missing'/'report.json')

if __name__ == '__main__': unittest.main()
