"""Regression tests for adversarial round 7: setup-flow robustness and approve concurrency."""
import tempfile
import threading
import unittest
from pathlib import Path
from adm import firstrun, intake
from adm.engine import SafetyError


class FirstrunRobustnessTests(unittest.TestCase):
    def test_assess_survives_a_broken_python_finder(self):
        def boom():
            raise RuntimeError('finder exploded')
        a = firstrun.assess(inspect=lambda **k: {'installed_models': []}, ram_gib=16, python_finder=boom)
        self.assertIsInstance(a, dict)
        self.assertFalse(a['python']['found'])
        self.assertIn('python', a['needs'])

    def test_assess_survives_hostile_inspect_results(self):
        for inspect in (lambda **k: {}, lambda **k: 'not a dict', lambda **k: {'installed_models': 'x'}):
            a = firstrun.assess(inspect=inspect, ram_gib=16)
            self.assertIsInstance(a, dict)

    def test_pull_rejects_unapproved_model(self):
        with self.assertRaises(ValueError):
            firstrun.pull_with_progress('ollama', 'definitely-not-approved:latest', lambda s: None)

    def test_run_setup_requires_approval(self):
        a = firstrun.assess(inspect=lambda **k: {'installed_models': []}, ram_gib=16)
        with self.assertRaises(Exception):
            firstrun.run_setup(a, approved=False, on_status=lambda s: None)


class ApproveConcurrencyTests(unittest.TestCase):
    def test_concurrent_approve_never_crashes_and_approves(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = base / 'home'; home.mkdir()
            ans = {'title': 'C', 'summary': 's', 'features': ['f'], 'tests': ['t'],
                   'needs_internet': False, 'questions': []}
            plan = intake.create_plan(base / 'state', 'a concurrently approved tool', mode='new', folder='',
                                      generator=lambda m, p, t: ans, model='ollama/x', home=home)
            errors, oks = [], []
            def go():
                try:
                    oks.append(intake.approve(plan['path'])['status'])
                except SafetyError:
                    errors.append('rejected')
                except Exception as exc:
                    errors.append(f'{type(exc).__name__}: {exc}')
            threads = [threading.Thread(target=go) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual([e for e in errors if ':' in e], [])   # no uncaught exceptions
            self.assertIn('approved', oks)


if __name__ == '__main__':
    unittest.main()
