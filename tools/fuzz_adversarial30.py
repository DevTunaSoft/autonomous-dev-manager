"""ADM-054 fuzz round 30: prevent phantom acceptance-test coverage.

Randomly generate valid-looking test sources with N real discoverable methods,
then ask the validator to enforce N+1 requirements. Reject duplicate names,
skips and non-discoverable top-level test functions.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.build import validate_tests
from adm.engine import SafetyError

rng = random.Random(54030)
errors = []
checks = 0


def source_for(n):
    names = [f"test_check_{i}" for i in range(n)]
    return (
        "import unittest, app\n"
        "class TestRequirement(unittest.TestCase):\n"
        + "".join(f"    def {name}(self):\n"
                  f"        self.assertEqual(app.calculate({i}), {i})\n"
                  for i, name in enumerate(names))
    )


def envelope(src):
    return {'files': [{'path': 'test_app.py', 'content': src}]}


for i in range(300):
    size = rng.randint(1, 16)
    src = source_for(size)
    try:
        assert validate_tests(envelope(src), required_checks=size) == src
        checks += 1
        try:
            validate_tests(envelope(src), required_checks=size + 1)
            errors.append(f'[{i}] accepted {size} tests for {size + 1} checks')
        except SafetyError:
            checks += 1
        if size > 1:
            names = {f'test_check_{j}' for j in range(size)}
            try:
                validate_tests(envelope(src), required_checks=1, previous_names=names)
                errors.append(f'[{i}] accepted amendment without a newly named test')
            except SafetyError:
                checks += 1
    except BaseException as exc:
        errors.append(f'[{i}] unexpected {type(exc).__name__}: {exc}')

for index in range(400):
    count = rng.randint(1, 8)
    src = source_for(count)
    mode = rng.choice(['duplicate', 'skip', 'decorator', 'fake', 'badshape'])
    if mode == 'duplicate':
        # Changing the last method's name duplicates an earlier method and
        # makes a method disappear at runtime.
        src = src.replace(f'def test_check_{count-1}(self):', 'def test_check_0(self):') if count > 1 else (
            src.replace("    def test_check_0(self):",
                        "    def test_check_0(self):\n        self.assertTrue(True)\n    def test_check_0(self):"))
    elif mode == 'skip':
        src = src.replace('    def test_check_0(self):',
                          "    @unittest.skip('not done')\n    def test_check_0(self):")
    elif mode == 'decorator':
        src = src.replace('    def test_check_0(self):',
                          '    @staticmethod\n    def test_check_0(self):')
    elif mode == 'fake':
        src = ("import unittest, app\n" +
               "\n".join(f"def test_unused_{k}():\n    assert app.ok()" for k in range(count)) +
               "\nclass TestRequirement(unittest.TestCase):\n"
               "    def test_check_0(self):\n        self.assertTrue(app.ok())\n")
    else:
        src = {'malformed': True}
    try:
        validate_tests(envelope(src), required_checks=(count+1 if mode == 'fake' else count))
        errors.append(f'[{index}] accepted hostile {mode}')
    except SafetyError:
        checks += 1
    except BaseException as exc:
        errors.append(f'[{index}] {mode} threw {type(exc).__name__}: {exc}')

print(f'ADM-054 coverage adversarial checks={checks}, errors={len(errors)}')
for issue in errors[:20]:
    print(issue)
if errors:
    raise SystemExit(1)
