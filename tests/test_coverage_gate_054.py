"""ADM-054: generated acceptance checks must have discoverable test methods."""
import random
import tempfile
import unittest
from pathlib import Path

from adm import build, intake
from adm.engine import SafetyError

TWO_TESTS = (
    "import unittest\nfrom app import add\n"
    "class Checks(unittest.TestCase):\n"
    "    def test_one(self):\n        self.assertEqual(add(2, 3), 5)\n"
    "    def test_two(self):\n        self.assertEqual(add(0, 0), 0)\n"
)


def reply(source):
    return {'files': [{'path': 'test_app.py', 'content': source}]}


class AcceptanceCoverageTests(unittest.TestCase):
    def test_exact_required_method_count(self):
        self.assertEqual(build.validate_tests(reply(TWO_TESTS), required_checks=2), TWO_TESTS)
        with self.assertRaisesRegex(SafetyError, 'fewer methods'):
            build.validate_tests(reply(TWO_TESTS), required_checks=3)

    def test_existing_noncoverage_validator_remains_compatible(self):
        self.assertEqual(build.validate_tests(reply(TWO_TESTS)), TWO_TESTS)

    def test_only_discoverable_unittest_tests_count(self):
        raw = (
            "import unittest\nfrom app import add\n"
            "def test_fake():\n    assert add(1, 1) == 2\n"
            "class NotATest:\n"
            "    def test_fake_two(self):\n        assert add(1, 1) == 2\n"
            "class Checks(unittest.TestCase):\n"
            "    def test_real(self):\n        self.assertEqual(add(1, 2), 3)\n"
        )
        with self.assertRaises(SafetyError):
            build.validate_tests(reply(raw), required_checks=2)
        self.assertEqual(build.validate_tests(reply(raw), required_checks=1), raw)

    def test_duplicate_test_methods_do_not_falsely_increase_count(self):
        raw = (
            "import unittest, app\n"
            "class Checks(unittest.TestCase):\n"
            "    def test_duplicate(self):\n        self.assertTrue(app.ok())\n"
            "    def test_duplicate(self):\n        self.assertTrue(app.ok())\n"
        )
        with self.assertRaisesRegex(SafetyError, 'redefine'):
            build.validate_tests(reply(raw), required_checks=2)

    def test_duplicate_classes_are_refused(self):
        raw = (
            "import unittest, app\n"
            "class Checks(unittest.TestCase):\n"
            "    def test_first(self):\n        self.assertTrue(app.ok())\n"
            "class Checks(unittest.TestCase):\n"
            "    def test_second(self):\n        self.assertTrue(app.ok())\n"
        )
        with self.assertRaisesRegex(SafetyError, 'class twice'):
            build.validate_tests(reply(raw), required_checks=2)

    def test_skip_decorator_is_not_accepted(self):
        raw = (
            "import unittest, app\n"
            "class Checks(unittest.TestCase):\n"
            "    @unittest.skip('not yet implemented')\n"
            "    def test_skip(self):\n        self.assertTrue(app.ok())\n"
        )
        with self.assertRaisesRegex(SafetyError, 'skip approved'):
            build.validate_tests(reply(raw), required_checks=1)

    def test_decorators_cannot_hide_or_transform_approved_methods(self):
        for decorator in ("@unittest.expectedFailure", "@staticmethod",
                          "@classmethod", "@property"):
            raw = ("import unittest, app\nclass Checks(unittest.TestCase):\n"
                   f"    {decorator}\n"
                   "    def test_hidden(self):\n"
                   "        self.assertTrue(app.ok())\n")
            with self.subTest(decorator=decorator), self.assertRaisesRegex(
                    SafetyError, 'Decorated test methods'):
                build.validate_tests(reply(raw), required_checks=1)

    def test_decorated_class_is_refused(self):
        raw = ("import unittest, app\n"
               "@unittest.skip('all tests skipped')\n"
               "class Checks(unittest.TestCase):\n"
               "    def test_hidden(self):\n        self.assertTrue(app.ok())\n")
        with self.assertRaisesRegex(SafetyError, 'skip a test class'):
            build.validate_tests(reply(raw), required_checks=1)

    def test_nonasserting_methods_are_not_accepted(self):
        raw = (
            "import unittest, app\n"
            "class Checks(unittest.TestCase):\n"
            "    def test_real(self):\n        self.assertTrue(app.ok())\n"
            "    def test_unchecked(self):\n        pass\n"
        )
        with self.assertRaisesRegex(SafetyError, 'Every generated'):
            build.validate_tests(reply(raw), required_checks=2)

    def test_testcase_alias_is_supported(self):
        raw = ("from unittest import TestCase as Case\nimport app\n"
               "class Checks(Case):\n"
               "    def test_real(self):\n        self.assertTrue(app.ok())\n")
        self.assertEqual(build.validate_tests(reply(raw), required_checks=1), raw)

    def test_rename_does_not_count_as_new_amend_check(self):
        with self.assertRaisesRegex(SafetyError, 'omitted new'):
            build.validate_tests(reply(TWO_TESTS), required_checks=1,
                                 previous_names={'test_one', 'test_two'})
        self.assertEqual(build.validate_tests(reply(TWO_TESTS), required_checks=1,
                                              previous_names={'test_one'}), TWO_TESTS)

    def test_invalid_check_count_and_prior_inventory_fail_closed(self):
        for value in (-1, 21, None, True, 2.0, '2', [], {}):
            with self.subTest(value=repr(value)), self.assertRaises(SafetyError):
                build.validate_tests(reply(TWO_TESTS), required_checks=value)
        with self.assertRaises(SafetyError):
            build.validate_tests(reply(TWO_TESTS), required_checks=1, previous_names=['test_one'])

    def test_seeded_generated_method_coverage(self):
        rng = random.Random(54)
        for _ in range(120):
            count = rng.randint(1, 6)
            text = ("import unittest, app\nclass Checks(unittest.TestCase):\n" +
                    ''.join(f"    def test_check_{i}(self):\n"
                            f"        self.assertEqual(app.check({i}), {i})\n"
                            for i in range(count)))
            self.assertEqual(build.validate_tests(reply(text), required_checks=count), text)
            with self.assertRaises(SafetyError):
                build.validate_tests(reply(text), required_checks=count + 1)

    def test_incomplete_tests_block_code_generation_before_scaffold(self):
        answer = {'title': 'Adder', 'summary': 'A simple addition program.',
                  'features': ['Add numbers'],
                  'tests': ['When 2 and 3 are added, get 5',
                            'When 0 and 0 are added, get 0'],
                  'needs_internet': False, 'questions': []}
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / 'home'
            home.mkdir()
            state = Path(tmp) / 'state'
            plan = intake.create_plan(state, 'Build an addition app', mode='new', folder='',
                                      generator=lambda *a, **kw: answer,
                                      model='ollama/local', home=home)
            approved = intake.approve(plan['path'])
            one_test = TWO_TESTS.replace(
                "    def test_two(self):\n        self.assertEqual(add(0, 0), 0)\n", '')
            with self.assertRaisesRegex(SafetyError, 'fewer methods'):
                build.build_from_plan(
                    approved['path'], Path(tmp) / 'evidence',
                    test_generator=lambda *a, **kw: reply(one_test),
                    code_generator=lambda *a, **kw: self.fail('code generator must not run'),
                    model='ollama/local', runner=None, require_sandbox=False)
            folder = Path(approved['folder'])
            self.assertFalse((folder / 'app.py').exists())
            self.assertFalse((folder / 'test_app.py').exists())


if __name__ == '__main__':
    unittest.main()
