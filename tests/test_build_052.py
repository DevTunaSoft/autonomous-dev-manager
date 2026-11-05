import json, tempfile, unittest
from pathlib import Path
from adm import build, intake
from adm.engine import SafetyError, run_checked

PLAN_ANSWER = {'title': 'Tip calculator',
               'summary': 'Works out a tip and splits a bill between people.',
               'features': ['Add a tip to a bill', 'Split a total between people'],
               'tests': ['When the bill is 100 and the tip is 20 percent, the total is 120',
                         'When 120 is split between 4 people, each pays 30',
                         'When the tip is 0 percent, the total equals the bill'],
               'needs_internet': False, 'questions': []}

GOOD_TESTS = ('import unittest\n'
              'from app import tip_total, per_person\n\n'
              'class T(unittest.TestCase):\n'
              '    def test_total(self):\n        self.assertEqual(tip_total(100, 20), 120)\n'
              '    def test_split(self):\n        self.assertEqual(per_person(120, 4), 30)\n'
              '    def test_zero(self):\n        self.assertEqual(tip_total(100, 0), 100)\n\n'
              "if __name__ == '__main__':\n    unittest.main()\n")

GOOD_CODE = ('def tip_total(bill, tip_percent):\n    return bill + bill * tip_percent / 100\n\n'
             'def per_person(total, people):\n    return total / people\n')


def test_gen(content=GOOD_TESTS):
    def g(model, prompt, timeout=300):
        return {'files': [{'path': 'test_app.py', 'content': content}]}
    return g


def code_gen(content=GOOD_CODE):
    def g(model, prompt, timeout=300):
        return {'files': [{'path': 'app.py', 'content': content}]}
    return g


def failing_code_gen():
    n = [0]
    def g(model, prompt, timeout=300):
        n[0] += 1
        return {'files': [{'path': 'app.py', 'content': f'def tip_total(b, t):\n    return 0  # try {n[0]}\n'
                                                        f'def per_person(t, p):\n    return 0\n'}]}
    return g


def sandbox_runner():
    def r(argv, cwd, root, timeout=90, output_limit=30000):
        return run_checked(argv, cwd, root, timeout=timeout)
    r.adm_isolation = 'sandbox'
    return r


class BuildStageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.state = self.base / 'state'
        self.home = self.base / 'home'
        self.home.mkdir()

    def approved_plan(self, answer=PLAN_ANSWER):
        def g(model, prompt, timeout): return answer
        plan = intake.create_plan(self.state, 'A tip calculator that splits the bill',
                                  mode='new', folder='', generator=g, model='ollama/x', home=self.home)
        return intake.approve(plan['path'])

    def build(self, plan, **kw):
        args = dict(test_generator=test_gen(), code_generator=code_gen(), model='ollama/x',
                    runner=None, require_sandbox=False)
        args.update(kw)
        return build.build_from_plan(plan['path'], self.base / f'ev-{id(kw)}', **args)

    # --- the gate -----------------------------------------------------
    def test_requires_an_approved_plan(self):
        def g(model, prompt, timeout): return PLAN_ANSWER
        plan = intake.create_plan(self.state, 'A tip calculator that splits the bill',
                                  mode='new', folder='', generator=g, model='ollama/x', home=self.home)
        with self.assertRaises(SafetyError):
            self.build(plan)       # never approved

    # --- the happy path ----------------------------------------------
    def test_builds_and_verifies_against_frozen_tests(self):
        plan = self.approved_plan()
        report = self.build(plan)
        self.assertEqual(report['status'], 'built')
        self.assertEqual(report['repair']['status'], 'verified_direct_repair')
        root = Path(plan['folder'])
        self.assertIn('tip_total', (root / 'app.py').read_text())
        # the tests and requirements were frozen: still exactly what was scaffolded
        self.assertEqual((root / 'test_app.py').read_text(), GOOD_TESTS)
        self.assertEqual(json.loads((root / 'requirements.json').read_text())['title'], 'Tip calculator')

    def test_sandbox_runner_is_accepted_and_recorded(self):
        plan = self.approved_plan()
        report = self.build(plan, runner=sandbox_runner(), require_sandbox=True)
        self.assertEqual(report['status'], 'built')
        self.assertEqual(report['isolation'], 'sandbox')

    # --- the honesty guards ------------------------------------------
    def test_trivial_tests_that_pass_before_code_are_rejected(self):
        trivial = ('import unittest, app\n\nclass T(unittest.TestCase):\n'
                   '    def test_nothing(self):\n        self.assertTrue(True)\n')
        plan = self.approved_plan()
        report = self.build(plan, test_generator=test_gen(trivial))
        self.assertEqual(report['status'], 'rejected_trivial_tests')
        self.assertEqual(report['repair']['status'], 'baseline_passed')

    def test_build_that_never_passes_reports_could_not_build(self):
        plan = self.approved_plan()
        report = self.build(plan, code_generator=failing_code_gen(), max_repairs=2)
        self.assertEqual(report['status'], 'could_not_build')
        self.assertNotIn(report['repair']['status'], ('verified_direct_repair', 'baseline_passed'))

    def test_refuses_to_run_without_sandbox_by_default(self):
        plan = self.approved_plan()
        with self.assertRaises(SafetyError):
            build.build_from_plan(plan['path'], self.base / 'ev-x', test_generator=test_gen(),
                                  code_generator=code_gen(), model='ollama/x', runner=None)
        with self.assertRaises(SafetyError):
            build.build_from_plan(plan['path'], self.base / 'ev-y', test_generator=test_gen(),
                                  code_generator=code_gen(), model='ollama/x',
                                  runner=run_checked)   # a plain runner is not the sandbox

    # --- scaffold -----------------------------------------------------
    def test_scaffold_refuses_to_overwrite_existing_files(self):
        plan = self.approved_plan()
        (Path(plan['folder']) / 'app.py').write_text('my own work')
        with self.assertRaises(SafetyError):
            self.build(plan)
        self.assertEqual((Path(plan['folder']) / 'app.py').read_text(), 'my own work')

    # --- test validation ---------------------------------------------
    def test_validate_tests_rejects_bad_answers(self):
        bad = [
            {'files': []},
            {'files': [{'path': 'test_app.py', 'content': 'x'}, {'path': 'test_b.py', 'content': 'y'}]},
            {'files': [{'path': 'tests.py', 'content': GOOD_TESTS}]},
            {'files': [{'path': 'test_app.py', 'content': 'import unittest\nclass T(unittest.TestCase):\n def test_x(self):\n  self.assertTrue(1)\n'}]},  # no app import
            {'files': [{'path': 'test_app.py', 'content': 'import app\nx = 1\n'}]},  # no test methods
            {'files': [{'path': 'test_app.py', 'content': 'import app\ndef test_x():\n    pass\n'}]},  # no assertions
            {'files': [{'path': 'test_app.py', 'content': 'import app\ndef test_x(: pass'}]},  # syntax error
        ]
        for answer in bad:
            with self.assertRaises(SafetyError, msg=str(answer)[:70]):
                build.validate_tests(answer)

    def test_validate_tests_accepts_a_real_test_file(self):
        self.assertEqual(build.validate_tests({'files': [{'path': 'test_app.py', 'content': GOOD_TESTS}]}), GOOD_TESTS)

    # --- run_build (the path the dashboard uses) ----------------------
    def test_run_build_keeps_evidence_outside_the_project_and_saves_a_report(self):
        plan = self.approved_plan()
        report = build.run_build(self.state, plan['path'], test_generator=test_gen(),
                                 code_generator=code_gen(), model='ollama/x',
                                 runner=sandbox_runner(), require_sandbox=True)
        self.assertEqual(report['status'], 'built')
        ev = Path(report['evidence']).resolve()
        root = Path(plan['folder']).resolve()
        self.assertNotEqual(ev, root)
        self.assertNotIn(root, ev.parents)           # evidence is NOT inside the project
        saved = build.builds_root(self.state) / (report['plan_id'] + '.json')
        self.assertTrue(saved.is_file())
        self.assertEqual(json.loads(saved.read_text())['status'], 'built')
        self.assertEqual(report['checks'], plan['content']['tests'])


if __name__ == '__main__':
    unittest.main()
