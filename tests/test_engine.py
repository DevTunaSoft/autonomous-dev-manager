import json
import sys
import tempfile
import unittest
from pathlib import Path
from adm.engine import SafetyError, make_broken_demo, proof, run_checked, demo_repair, inside


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.project = make_broken_demo(self.base / 'project')
        self.evidence = self.base / 'evidence'

    def tearDown(self):
        self.tmp.cleanup()

    def test_end_to_end_repair(self):
        result = proof(self.project, self.evidence)
        self.assertEqual(result['status'], 'verified_demo')
        self.assertNotEqual(result['tests'][0]['exit_code'], 0)
        self.assertEqual(result['tests'][-1]['exit_code'], 0)
        self.assertNotEqual(result['repair']['before_sha256'], result['repair']['after_sha256'])
        self.assertTrue((self.evidence / 'proof-report.json').exists())

    def test_interrupted_resume(self):
        first = proof(self.project, self.evidence, interrupt_after_failure=True)
        self.assertEqual(first['status'], 'interrupted_after_failure')
        second = proof(self.project, self.evidence)
        self.assertEqual(second['status'], 'verified_demo')
        self.assertEqual(len(second['tests']), 2)

    def test_no_false_success_when_repair_fails(self):
        result = proof(self.project, self.evidence, repair=lambda _: False)
        self.assertEqual(result['status'], 'failed')

    def test_no_overwrite(self):
        with self.assertRaises(SafetyError):
            make_broken_demo(self.project)

    def test_cwd_escape_blocked(self):
        with self.assertRaises(SafetyError):
            run_checked([sys.executable, '-c', 'print(1)'], self.base, self.project)

    def test_command_timeout(self):
        result = run_checked([sys.executable, '-c', 'import time;time.sleep(2)'], self.project, self.project, timeout=0.1)
        self.assertEqual(result['exit_code'], 124)

    def test_safe_path(self):
        self.assertTrue(inside(self.project, self.project))
        self.assertFalse(inside(self.base, self.project))

    def test_command_argument_validation(self):
        with self.assertRaises(SafetyError):
            run_checked([], self.project, self.project)

    def test_evidence_not_inside_project(self):
        with self.assertRaises(SafetyError):
            proof(self.project, self.project / 'evidence')


if __name__ == '__main__':
    unittest.main()
