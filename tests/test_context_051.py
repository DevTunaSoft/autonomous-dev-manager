"""ADM-051: what the model reads is reduced; what is tested and recorded is not."""
import json
import tempfile
import unittest
from pathlib import Path

from adm.context import (excerpt_failure, failing_tests, traceback_files, failure_signature,
                         AttemptLedger, check_patch, build_repair_prompt)
from adm.engine import SafetyError, make_broken_demo
from adm.ollama_direct import direct_repair

UNITTEST_OUTPUT = '''test_a (test_m.T.test_a) ... FAIL
test_b (test_m.T.test_b) ... ERROR
test_c (test_m.T.test_c) ... ok

======================================================================
ERROR: test_b (test_m.T.test_b)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "{root}/test_m.py", line 9, in test_b
    helper()
  File "{root}/app.py", line 4, in helper
    raise ValueError("boom")
ValueError: boom

======================================================================
FAIL: test_a (test_m.T.test_a)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "{root}/test_m.py", line 5, in test_a
    self.assertEqual(1, 2)
AssertionError: 1 != 2

----------------------------------------------------------------------
Ran 3 tests in 0.001s

FAILED (failures=1, errors=1)
'''


class ExcerptTests(unittest.TestCase):
    def test_short_output_is_passed_through_unchanged(self):
        view = excerpt_failure('FAIL: test_x (m.T.test_x)\nAssertionError: no\n', max_chars=3000)
        self.assertEqual(view['omitted_chars'], 0)
        self.assertIn('AssertionError: no', view['text'])

    def test_every_failing_test_is_named_even_when_output_is_shortened(self):
        noisy = ''.join(f'FAIL: test_{i} (m.T.test_{i})\n' + ('noise line %d\n' % i) * 40 for i in range(60))
        view = excerpt_failure(noisy, max_chars=1500)
        self.assertGreater(view['omitted_chars'], 0)
        self.assertEqual(len(view['failing_tests']), 60)
        self.assertTrue(view['all_failures_named'])
        for i in range(60):
            self.assertIn(f'm.T.test_{i}', view['text'])

    def test_repeated_lines_are_collapsed_and_tail_summary_kept(self):
        output = 'FAIL: test_a (m.T.test_a)\n' + 'same line\n' * 500 + 'AssertionError: final\nFAILED (failures=1)\n'
        view = excerpt_failure(output, max_chars=800)
        self.assertIn('repeated 500 times', view['text'])
        self.assertIn('FAILED (failures=1)', view['text'])
        self.assertLess(view['shown_chars'], 900)

    def test_view_says_where_full_output_is_saved(self):
        view = excerpt_failure('x\n' * 5000, max_chars=500, saved_to='baseline-output.log')
        self.assertIn('baseline-output.log', view['text'])

    def test_failing_test_parser(self):
        self.assertEqual(failing_tests(UNITTEST_OUTPUT), ['test_m.T.test_b', 'test_m.T.test_a'])

    def test_traceback_files_deepest_application_frame_first(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / 'app.py').write_text('x=1\n'); (root / 'test_m.py').write_text('y=1\n')
            files = traceback_files(UNITTEST_OUTPUT.replace('{root}', str(root)), root)
            self.assertEqual(files[0], 'test_m.py')       # last frame seen is the test's assertion
            self.assertIn('app.py', files)
            self.assertEqual(traceback_files('File "/etc/passwd", line 1', root), [])

    def test_signature_is_stable_and_changes_with_the_failure(self):
        a = failure_signature(UNITTEST_OUTPUT)
        self.assertEqual(a, failure_signature(UNITTEST_OUTPUT))
        self.assertNotEqual(a, failure_signature(UNITTEST_OUTPUT.replace('boom', 'bang')))


class LedgerAndPatchGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = make_broken_demo(Path(self.tmp.name) / 'p')

    def test_repeated_patch_is_recognised(self):
        ledger = AttemptLedger()
        patch = {'files': [{'path': 'calculator.py', 'content': 'x=1\n'}]}
        self.assertIsNone(ledger.seen_patch(patch))
        ledger.record(1, patch, UNITTEST_OUTPUT, ['calculator.py'])
        self.assertEqual(ledger.seen_patch({'files': [{'path': 'calculator.py', 'content': 'x=1\n'}]}), 1)
        self.assertIn('Attempt 1', ledger.notes())

    def test_stuck_means_same_failure_twice(self):
        ledger = AttemptLedger()
        ledger.record(1, None, UNITTEST_OUTPUT, [])
        self.assertFalse(ledger.stuck())
        ledger.record(2, None, UNITTEST_OUTPUT, [])
        self.assertTrue(ledger.stuck())

    def test_patch_guards(self):
        shown = {'calculator.py'}
        ok = {'files': [{'path': 'calculator.py', 'content': 'def add(a, b):\n    return a + b\n'}]}
        check_patch(self.root, ok, shown)
        cases = {
            'not shown in full': ({'files': [{'path': 'other.py', 'content': 'x=1'}]}, shown),
            'empty': ({'files': [{'path': 'calculator.py', 'content': '  \n'}]}, shown),
            'identical': ({'files': [{'path': 'calculator.py',
                                      'content': 'def add(a, b):\n    return a - b\n'}]}, shown),
            'placeholder': ({'files': [{'path': 'calculator.py',
                                        'content': 'def add(a, b):\n    return a + b\n# rest of the code unchanged\n'}]}, shown),
        }
        for label, (patch, allowed) in cases.items():
            with self.subTest(label), self.assertRaises(SafetyError):
                check_patch(self.root, patch, allowed)

    def test_truncation_guard(self):
        big = Path(self.root / 'calculator.py')
        big.write_text('def add(a, b):\n    return a - b\n' + '# padding\n' * 100)
        with self.assertRaises(SafetyError):
            check_patch(self.root, {'files': [{'path': 'calculator.py', 'content': 'def add(a,b): return a+b\n'}]},
                        {'calculator.py'})


class PromptTests(unittest.TestCase):
    def test_prompt_keeps_safety_instructions_notes_and_source(self):
        prompt = build_repair_prompt('{"requirements":[]}', 'FAIL view', 2, 'FILE a.py (shown in full):\nx=1', 'Attempt 1 failed.\n')
        for needle in ('Do not modify requirements.json', 'Only files shown in full', 'Attempt 1 failed.',
                       'FAIL view', 'FILE a.py'):
            self.assertIn(needle, prompt)


class LoopIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = make_broken_demo(self.base / 'p')

    def test_full_output_is_saved_and_report_names_failures(self):
        good = {'files': [{'path': 'calculator.py', 'content': 'def add(a, b):\n    return a + b\n'}]}
        report = direct_repair(self.root, self.base / 'ev', generator=lambda *a, **k: good)
        self.assertEqual(report['status'], 'verified_direct_repair')
        self.assertEqual(report['gate'], 'tests_only')
        self.assertTrue((self.base / 'ev' / 'baseline-output.log').is_file())
        view = report['attempts'][0]['failure_view']
        self.assertEqual(sorted(view['failing_tests']),
                         sorted(failing_tests((self.base / 'ev' / 'baseline-output.log').read_text())))
        self.assertTrue(view['all_failures_named'])

    def test_model_opinion_cannot_pass_the_gate(self):
        """A patch the model calls correct still fails if the tests fail."""
        wrong = {'files': [{'path': 'calculator.py', 'content': 'def add(a, b):\n    return 0  # looks good\n'}]}
        report = direct_repair(self.root, self.base / 'ev', max_repairs=1, generator=lambda *a, **k: wrong)
        self.assertEqual(report['status'], 'repair_failed')
        self.assertFalse(report['attempts'][0]['passed'])

    def test_repeated_patch_is_not_applied_twice_and_next_prompt_says_so(self):
        wrong = {'files': [{'path': 'calculator.py', 'content': 'def add(a, b):\n    return 0\n'}]}
        prompts = []
        def gen(model, prompt, timeout):
            prompts.append(prompt)
            return json.loads(json.dumps(wrong))
        report = direct_repair(self.root, self.base / 'ev', max_repairs=2, generator=gen)
        self.assertEqual(report['status'], 'repair_failed')
        self.assertIn('repeated the patch from attempt 1', report['attempts'][1]['error'])
        self.assertIn('Attempt 1 changed calculator.py', prompts[1])

    def test_rejection_keeps_real_test_output_for_next_attempt(self):
        prompts = []
        replies = iter([{'files': [{'path': 'calculator.py', 'content': ''}]},
                        {'files': [{'path': 'calculator.py', 'content': 'def add(a, b):\n    return a + b\n'}]}])
        def gen(model, prompt, timeout):
            prompts.append(prompt)
            return next(replies)
        report = direct_repair(self.root, self.base / 'ev', max_repairs=2, generator=gen)
        self.assertEqual(report['status'], 'verified_direct_repair')
        self.assertIn('AssertionError', prompts[1])             # still sees the real failure
        self.assertIn('rejected before testing', prompts[1])


if __name__ == '__main__':
    unittest.main()
