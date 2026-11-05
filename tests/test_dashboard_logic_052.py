"""Headless tests of the dashboard's pure logic (no Tk): stats and uptime formatting."""
import json, tempfile, unittest
from pathlib import Path
from adm import dashboard, intake, build


def _plan_gen(answer):
    def g(model, prompt, timeout):
        return answer
    return g


ANSWER = {'title': 'Timer', 'summary': 'A tiny timer.', 'features': ['Start a timer'],
          'tests': ['When started with 5, it counts down to 0'], 'needs_internet': False, 'questions': []}


class UptimeTests(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(dashboard._fmt_uptime(0), '0m')
        self.assertEqual(dashboard._fmt_uptime(59), '0m')
        self.assertEqual(dashboard._fmt_uptime(65 * 60), '1h 05m')
        self.assertEqual(dashboard._fmt_uptime(130 * 60), '2h 10m')

    def test_non_finite_and_bad_values_do_not_crash(self):
        for bad in (float('nan'), float('inf'), float('-inf'), -1, -999, None, 'x'):
            self.assertEqual(dashboard._fmt_uptime(bad), '0m')


class CollectStatsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.state = self.base / 'state'
        self.home = self.base / 'home'
        self.home.mkdir()

    def test_empty_state_is_all_zeros_and_dashes(self):
        s = dashboard.collect_stats(self.state)
        self.assertEqual((s['projects'], s['queue'], s['completed'], s['builds']), (0, 0, 0, 0))
        self.assertEqual(s['passing'], '—')

    def test_counts_approved_plans_and_built_reports(self):
        plan = intake.approve(intake.create_plan(self.state, 'a tiny timer app', mode='new', folder='',
                              generator=_plan_gen(ANSWER), model='ollama/x', home=self.home)['path'])
        # an unapproved plan should NOT be counted as a project
        intake.create_plan(self.state, 'another different idea entirely', mode='new', folder='',
                           generator=_plan_gen(dict(ANSWER, title='Other')), model='ollama/x', home=self.home)
        build.save_report(self.state, {'plan_id': plan['id'], 'status': 'built',
                                       'checks': plan['content']['tests']})
        s = dashboard.collect_stats(self.state)
        self.assertEqual(s['projects'], 1)       # only the approved one
        self.assertEqual(s['completed'], 1)
        self.assertEqual(s['passing'], '1/1')    # one check in the latest built report

    def test_a_failed_build_report_is_not_counted_completed(self):
        plan = intake.approve(intake.create_plan(self.state, 'a tiny timer app', mode='new', folder='',
                              generator=_plan_gen(ANSWER), model='ollama/x', home=self.home)['path'])
        build.save_report(self.state, {'plan_id': plan['id'], 'status': 'could_not_build', 'checks': []})
        s = dashboard.collect_stats(self.state)
        self.assertEqual(s['completed'], 0)
        self.assertEqual(s['passing'], '—')

    def test_corrupt_reports_and_plans_do_not_crash(self):
        # A report or plan.json may be hand-edited or corrupt: wrong top-level
        # type, or a 'checks' field that isn't a list. Stats must still compute.
        (self.state / 'builds').mkdir(parents=True, exist_ok=True)
        (self.state / 'plans' / 'bad').mkdir(parents=True, exist_ok=True)
        (self.state / 'builds' / '001.json').write_text(
            json.dumps({'status': 'built', 'checks': 5}), encoding='utf-8')      # checks not a list
        (self.state / 'builds' / '002.json').write_text(
            json.dumps(['not', 'a', 'dict']), encoding='utf-8')                  # top-level array
        (self.state / 'builds' / '003.json').write_text('garbage{', encoding='utf-8')
        (self.state / 'plans' / 'bad' / 'plan.json').write_text('nope{', encoding='utf-8')
        s = dashboard.collect_stats(self.state)                                 # must not raise
        self.assertIsInstance(s['completed'], int)
        self.assertIn(s['passing'], ('100%', '—'))                              # built-with-0-real-checks


if __name__ == '__main__':
    unittest.main()
