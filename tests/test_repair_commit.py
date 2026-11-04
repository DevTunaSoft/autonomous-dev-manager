"""Fault-injection regression tests for the repair commit boundary."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from adm.engine import make_broken_demo
from adm.ollama_direct import direct_repair


class RepairCommitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = make_broken_demo(Path(self.temp.name) / 'project')
        self.evidence = Path(self.temp.name) / 'evidence'
        self.original = (self.root / 'calculator.py').read_bytes()

    @staticmethod
    def good_patch(*args, **kwargs):
        return {'files': [{'path': 'calculator.py', 'content': 'def add(a,b):\n    return a+b\n'}]}

    def test_success_clears_journal_before_publishing_verified(self):
        from adm.ollama_direct import atomic_json as real_write
        states = []
        def capture(path, report):
            if report.get('status') == 'verified_direct_repair':
                states.append((self.evidence / 'repair-journal.json').exists())
            return real_write(path, report)
        with patch('adm.ollama_direct.atomic_json', side_effect=capture):
            report = direct_repair(self.root, self.evidence, generator=self.good_patch)
        self.assertEqual(report['status'], 'verified_direct_repair')
        self.assertEqual(states, [False])
        self.assertFalse((self.evidence / 'repair-journal.json').exists())

    def test_commit_failure_never_publishes_success_and_restores_source(self):
        with patch('adm.ollama_direct.finish_journal', side_effect=OSError('disk failure')):
            report = direct_repair(self.root, self.evidence, generator=self.good_patch, max_repairs=1)
        self.assertEqual(report['status'], 'repair_failed')
        self.assertEqual((self.root / 'calculator.py').read_bytes(), self.original)
        persisted = json.loads((self.evidence / 'ollama-direct-report.json').read_text())
        self.assertNotEqual(persisted['status'], 'verified_direct_repair')
        self.assertFalse((self.evidence / 'repair-journal.json').exists())

if __name__ == '__main__':
    unittest.main()
