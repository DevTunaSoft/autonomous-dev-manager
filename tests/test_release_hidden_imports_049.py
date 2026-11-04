import unittest
from pathlib import Path
from adm.release import windows_desktop_build_plan
from adm.selftest import SMOKE_MODULES


class ReleasePlanTests(unittest.TestCase):
    def test_desktop_plan_declares_every_smoke_module(self):
        plan = windows_desktop_build_plan(Path(__file__).resolve().parent.parent)
        for name in SMOKE_MODULES:
            i = plan.index(name)
            self.assertEqual(plan[i - 1], '--hidden-import')


if __name__ == '__main__':
    unittest.main()
