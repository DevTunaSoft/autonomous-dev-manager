"""Regression acceptance guards against vacuous or mistargeted successes."""
import tempfile
import unittest
from pathlib import Path
from adm.regression import run_suite

class RegressionGuards(unittest.TestCase):
    def test_empty_module_does_not_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'tests').mkdir()
            (root/'tests'/'test_empty.py').write_text('VALUE = 1\n')
            report=run_suite(root,timeout_per_module=10)
            self.assertFalse(report['passed'])
            self.assertEqual(report['modules'][0]['status'],'no_tests')
            self.assertEqual(report['total_tests'],0)

    def test_unknown_selected_module_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'tests').mkdir()
            (root/'tests'/'test_real.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_a(self): pass\n')
            with self.assertRaisesRegex(ValueError,'Unknown test modules'):
                run_suite(root,selected_modules={'test_typo.py'})

    def test_real_module_still_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'tests').mkdir()
            (root/'tests'/'test_real.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_a(self): pass\n')
            report=run_suite(root,selected_modules={'test_real.py'},timeout_per_module=10)
            self.assertTrue(report['passed'])
            self.assertEqual(report['total_tests'],1)
