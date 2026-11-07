"""ADM-055 fuzz round 31: previous acceptance behavior must be immutable."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.build import ensure_existing_tests_unchanged
from adm.engine import SafetyError

rng = random.Random(55031)
checked = 0
issues = []

for cycle in range(350):
    n = rng.randrange(1, 9)
    old = ("import unittest, app\n" +
           f"CONFIG = {n}\n" +
           "class Coverage(unittest.TestCase):\n"
           "    def setUp(self):\n        self.x = 1\n" +
           ''.join(f"    def test_prior_{k}(self):\n"
                   f"        self.assertEqual(app.run({k}), {k})\n"
                   for k in range(n)))
    plus = ("    def test_new(self):\n"
            "        self.assertEqual(app.run(100), 100)\n")
    valid = old + plus
    try:
        ensure_existing_tests_unchanged(old, valid)
        checked += 1
    except BaseException as exc:
        issues.append(f'[valid {cycle}] {type(exc).__name__}: {exc}')
    mode = rng.choice(('assertion', 'setup', 'class', 'constant', 'import',
                       'rename', 'remove', 'module', 'duplicate'))
    if mode == 'assertion':
        corrupted = valid.replace("self.assertEqual(app.run(0), 0)",
                                  "self.assertEqual(app.run(0), 999)")
    elif mode == 'setup':
        corrupted = valid.replace("self.x = 1", "self.x = 999")
    elif mode == 'class':
        corrupted = valid.replace("Coverage(unittest.TestCase)", "Coverage(object)")
    elif mode == 'constant':
        corrupted = valid.replace(f"CONFIG = {n}", "CONFIG = 999")
    elif mode == 'import':
        corrupted = valid.replace("import unittest, app", "import unittest")
    elif mode == 'rename':
        corrupted = valid.replace("def test_prior_0", "def test_previous_0")
    elif mode == 'remove':
        corrupted = valid.replace("        self.assertEqual(app.run(0), 0)\n", "        pass\n")
    elif mode == 'module':
        corrupted = valid.replace("import unittest, app", "import app")
    else:
        corrupted = valid + "\nclass Coverage(unittest.TestCase):\n    pass\n"
    try:
        ensure_existing_tests_unchanged(old, corrupted)
        issues.append(f'[invalid {cycle}] accepted change {mode}')
    except SafetyError:
        checked += 1
    except BaseException as exc:
        issues.append(f'[invalid {cycle}] {mode} threw {type(exc).__name__}: {exc}')

for invalid in (None, 123, {}, [], "\x00", "def broken(:"):
    try:
        ensure_existing_tests_unchanged(invalid, "import app")
        issues.append(f'[shape {invalid!r}] accepted invalid')
    except SafetyError:
        checked += 1
    except BaseException as exc:
        issues.append(f'[shape {invalid!r}] unexpected {type(exc).__name__}')

print(f'ADM-055 immutable-test fuzz checks={checked}, errors={len(issues)}')
for issue in issues[:25]:
    print(issue)
if issues:
    raise SystemExit(1)
