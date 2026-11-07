"""ADM-055: amendment must not weaken previously approved test behavior."""
import random
import unittest

from adm.build import ensure_existing_tests_unchanged
from adm.engine import SafetyError

OLD = (
    "import unittest\n"
    "from app import total\n"
    "THRESHOLD = 10\n"
    "def helper(v):\n    return v + 1\n"
    "class Tests(unittest.TestCase):\n"
    "    limit = 42\n"
    "    def setUp(self):\n        self.value = 4\n"
    "    def test_total(self):\n"
    "        self.assertEqual(total(self.value), THRESHOLD)\n"
    "if __name__ == '__main__':\n    unittest.main()\n"
)

# A legitimate amendment may insert new imports/methods while preserving all
# previously approved assertions, helper functions, fixtures and constants.
GOOD = OLD.replace(
    "from app import total\n", "from app import total, extra\n"
).replace(
    "    def test_total(self):\n",
    "    def test_extra(self):\n"
    "        self.assertEqual(extra(7), 8)\n"
    "    def test_total(self):\n"
)


class PreserveExistingTests(unittest.TestCase):
    def test_additive_amendment_succeeds(self):
        self.assertIsNone(ensure_existing_tests_unchanged(OLD, GOOD))

    def test_whitespace_and_comments_not_considered_weakening(self):
        revised = GOOD.replace("self.assertEqual(total(self.value), THRESHOLD)",
                               "self.assertEqual( total(self.value),  THRESHOLD ) # kept")
        ensure_existing_tests_unchanged(OLD, revised)

    def test_existing_assertions_cannot_be_weakened(self):
        for modified in (
            GOOD.replace("self.assertEqual(total(self.value), THRESHOLD)", "self.assertTrue(True)"),
            GOOD.replace("THRESHOLD)\n", "0)\n"),
            GOOD.replace("def test_total(self)", "def test_total_changed(self)"),
        ):
            with self.subTest(sample=modified[-75:]), self.assertRaises(SafetyError):
                ensure_existing_tests_unchanged(OLD, modified)

    def test_existing_fixture_must_stay(self):
        with self.assertRaises(SafetyError):
            ensure_existing_tests_unchanged(OLD, GOOD.replace("self.value = 4", "self.value = 0"))

    def test_existing_class_attribute_must_stay(self):
        with self.assertRaises(SafetyError):
            ensure_existing_tests_unchanged(OLD, GOOD.replace("limit = 42", "limit = 0"))

    def test_existing_class_hierarchy_must_stay(self):
        with self.assertRaisesRegex(SafetyError, 'inheritance'):
            ensure_existing_tests_unchanged(OLD, GOOD.replace("Tests(unittest.TestCase)",
                                                              "Tests(object)"))

    def test_existing_imports_must_remain(self):
        for revised in (
            GOOD.replace("from app import total, extra", "from app import extra"),
            GOOD.replace("import unittest\n", ""),
        ):
            with self.subTest(sample=revised[:80]), self.assertRaisesRegex(SafetyError, 'import'):
                ensure_existing_tests_unchanged(OLD, revised)

    def test_new_import_cannot_shadow_existing_test_dependency(self):
        # A later import with the same binding name would change the meaning
        # of the unchanged test method without touching the old assertion AST.
        edited = GOOD.replace("from app import total, extra\n",
                              "from app import total, extra\nfrom fake import total\n")
        with self.assertRaisesRegex(SafetyError, 'shadows'):
            ensure_existing_tests_unchanged(OLD, edited)

    def test_existing_helper_code_must_remain(self):
        for revised in (
            GOOD.replace("return v + 1", "return v + 100"),
            GOOD.replace("THRESHOLD = 10", "THRESHOLD = 0"),
            GOOD.replace("unittest.main()", "print('no tests')"),
        ):
            with self.subTest(sample=revised[:80]), self.assertRaisesRegex(SafetyError, 'helper or module'):
                ensure_existing_tests_unchanged(OLD, revised)

    def test_existing_class_and_methods_cannot_disappear(self):
        with self.assertRaisesRegex(SafetyError, 'removed or renamed'):
            ensure_existing_tests_unchanged(OLD, GOOD.replace("class Tests(", "class Other("))
        with self.assertRaises(SafetyError):
            ensure_existing_tests_unchanged(OLD, GOOD.replace(
                "    def test_total(self):\n        self.assertEqual(total(self.value), THRESHOLD)\n", ""))

    def test_duplicate_classes_not_trusted(self):
        with self.assertRaisesRegex(SafetyError, 'Duplicate class'):
            ensure_existing_tests_unchanged(OLD, GOOD + "\nclass Tests(unittest.TestCase):\n    pass\n")

    def test_bad_input_fails_closed(self):
        for before, after in ((None, OLD), (OLD, None), ({}, GOOD), (OLD, "def broken(:"),
                              (OLD + "\x00", GOOD), (OLD, GOOD + "\x00")):
            with self.subTest(before=repr(before)[:20]), self.assertRaises(SafetyError):
                ensure_existing_tests_unchanged(before, after)

    def test_deep_random_edit_comparisons(self):
        rng = random.Random(55)
        for _ in range(200):
            changed = rng.choice(['total(self.value)', 'self.value = 4', 'THRESHOLD = 10',
                                  'return v + 1', 'limit = 42'])
            edited = GOOD.replace(changed, changed + ' + 1')
            with self.subTest(changed=changed), self.assertRaises(SafetyError):
                ensure_existing_tests_unchanged(OLD, edited)


if __name__ == '__main__':
    unittest.main()
