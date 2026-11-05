import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from adm import diagnostics


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / 'state'

    def test_logging_writes_and_never_raises(self):
        diagnostics.log_line(self.state, 'hello world', component='test')
        self.assertTrue(diagnostics.log_path(self.state).is_file())
        self.assertIn('hello world', diagnostics.log_path(self.state).read_text())
        # even with a bad state path, logging must not raise
        diagnostics.log_line('\x00bad', 'x')          # no exception = pass

    def test_collect_is_resilient_and_structured(self):
        (self.state / 'plans' / 'p1').mkdir(parents=True)
        (self.state / 'plans' / 'p1' / 'plan.json').write_text('{"status": "approved"}')
        (self.state / 'plans' / 'p2').mkdir(parents=True)
        (self.state / 'plans' / 'p2' / 'plan.json').write_text('{ corrupt')
        (self.state / 'builds').mkdir(parents=True)
        (self.state / 'builds' / 'b1.json').write_text(json.dumps(
            {'plan_id': 'b1', 'status': 'built', 'mode': 'new', 'isolation': 'sandbox'}))
        info = diagnostics.collect(self.state)
        self.assertEqual(info['adm_version'], diagnostics.VERSION)
        self.assertEqual(info['plans_by_status'].get('approved'), 1)
        self.assertEqual(info['plans_by_status'].get('unreadable'), 1)
        self.assertEqual(info['recent_builds'][0]['status'], 'built')

    def test_self_check_returns_structured_results_and_never_raises(self):
        checks = diagnostics.self_check(self.state)
        self.assertIsInstance(checks, list)
        self.assertTrue(checks)
        for c in checks:
            self.assertIn('name', c)
            self.assertIn('ok', c)
            self.assertIsInstance(c['ok'], bool)
        names = {c['name'] for c in checks}
        self.assertIn('Python for your projects', names)
        self.assertIn('Disk space', names)
        # even with a nonsense state path, it must not raise
        diagnostics.self_check('\x00bad')

    def test_collect_includes_self_check(self):
        self.assertIn('self_check', diagnostics.collect(self.state))

    def test_export_bundle_is_a_valid_zip_without_source(self):
        diagnostics.log_line(self.state, 'start')
        (self.state / 'builds').mkdir(parents=True)
        (self.state / 'builds' / 'b1.json').write_text('{"plan_id":"b1","status":"built"}')
        ev = self.state / 'evidence' / 'b1'
        ev.mkdir(parents=True)
        (ev / 'baseline-output.log').write_text('FAILED test output here')
        (ev / 'app.py').write_text('SECRET SOURCE should NOT be bundled')   # not a .log / report
        dest = Path(self.tmp.name) / 'out' / 'bundle.zip'
        diagnostics.export_bundle(self.state, dest)
        self.assertTrue(dest.is_file())
        with zipfile.ZipFile(dest) as z:
            names = z.namelist()
            self.assertIn('diagnostics.json', names)
            self.assertIn('adm.log', names)
            self.assertIn('builds/b1.json', names)
            self.assertIn('evidence/b1/baseline-output.log', names)
            self.assertNotIn('evidence/b1/app.py', names)          # generated source is never included
            json.loads(z.read('diagnostics.json'))                 # valid JSON

    def test_safe_honours_caller_default_on_error(self):
        # _safe must return the caller's default (keeping the expected type) on
        # failure, and only fall back to a diagnostic string when none is given.
        self.assertEqual(diagnostics._safe(lambda: 1 / 0, {}), {})
        self.assertEqual(diagnostics._safe(lambda: 1 / 0, []), [])
        self.assertEqual(diagnostics._safe(lambda: 1 / 0, ''), '')
        self.assertEqual(diagnostics._safe(lambda: 7, {}), 7)        # success passes through
        r = diagnostics._safe(lambda: 1 / 0)                         # no default -> string
        self.assertIsInstance(r, str)
        self.assertTrue(r.startswith('unavailable'))

    def test_collect_keeps_types_when_reports_and_plans_are_corrupt(self):
        # A plan.json or build report may be a JSON array or garbage. collect()
        # must still return a dict for plans, lists for builds/self_check, str log.
        (self.state / 'plans' / 'bad').mkdir(parents=True, exist_ok=True)
        (self.state / 'plans' / 'bad' / 'plan.json').write_text('["array","not","object"]')
        (self.state / 'builds').mkdir(parents=True, exist_ok=True)
        (self.state / 'builds' / '001.json').write_text('[1,2,3]')
        (self.state / 'builds' / '002.json').write_text('garbage{')
        self.assertIsInstance(diagnostics._plan_counts(self.state), dict)   # must not raise
        self.assertIsInstance(diagnostics._recent_builds(self.state), list)
        info = diagnostics.collect(self.state)
        self.assertIsInstance(info['plans_by_status'], dict)
        self.assertIsInstance(info['recent_builds'], list)
        self.assertIsInstance(info['self_check'], list)
        self.assertIsInstance(info['log_tail'], str)


if __name__ == '__main__':
    unittest.main()
