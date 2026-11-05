"""Regression tests for adversarial round 8: agent helpers and Unicode slugs."""
import tempfile
import unittest
from pathlib import Path
from adm import agent, intake


class AtomicJsonTests(unittest.TestCase):
    def test_atomic_json_never_crashes_on_odd_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'r.json'
            agent.atomic_json(p, {'x': object(), 'y': [1, 2]})   # must not raise
            self.assertTrue(p.is_file())


class SlugTests(unittest.TestCase):
    def test_slug_is_always_a_safe_single_segment(self):
        for title in ['', '../escape', 'a/b\\c', 'null\x00here', '模型', '🤖🤖', 'CON', 'a' * 10000, '  ...  ']:
            slug = intake.slugify(title)
            self.assertTrue(slug and '/' not in slug and '\\' not in slug and '\x00' not in slug)
            self.assertNotIn('..', Path(slug).parts)


if __name__ == '__main__':
    unittest.main()
