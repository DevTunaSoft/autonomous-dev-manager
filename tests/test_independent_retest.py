"""Independent second-process verification of model-produced patches."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from adm.engine import make_broken_demo
from adm.ollama_direct import direct_repair

class IndependentRetestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = make_broken_demo(Path(self.temp.name) / 'project')
        self.evidence = Path(self.temp.name) / 'evidence'
        self.fix = lambda *a, **kw: {'files':[{'path':'calculator.py','content':'def add(a,b):\n return a+b\n'}]}

    def test_success_contains_two_passes(self):
        report = direct_repair(self.root, self.evidence, generator=self.fix)
        attempt = report['attempts'][0]
        self.assertTrue(attempt['passed'])
        self.assertEqual(attempt['test']['exit_code'], 0)
        self.assertEqual(attempt['independent_retest']['exit_code'], 0)

    def test_second_test_failure_rolls_back(self):
        from adm.ollama_direct import run_checked as real_run
        original = (self.root / 'calculator.py').read_bytes()
        calls = []
        def flaky(*args, **kwargs):
            calls.append(1)
            if len(calls) == 3:
                return {'exit_code': 1, 'output':'independent regression failure'}
            return real_run(*args, **kwargs)
        with patch('adm.ollama_direct.run_checked', side_effect=flaky):
            report = direct_repair(self.root, self.evidence, generator=self.fix, max_repairs=1)
        self.assertEqual(report['status'], 'repair_failed')
        self.assertFalse(report['attempts'][0]['passed'])
        self.assertEqual(report['attempts'][0]['independent_retest']['exit_code'], 1)
        self.assertEqual((self.root / 'calculator.py').read_bytes(), original)

if __name__ == '__main__':
    unittest.main()
