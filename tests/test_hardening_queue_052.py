"""Regression tests for adversarial round 4: queue, worker, lock, journal, status, build concurrency."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from adm import core, worker, daemon, repair_recovery, build, intake
from adm.engine import SafetyError, make_broken_demo
from adm.project_lock import exclusive_project


class QueueValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = make_broken_demo(self.base / 'job')

    def test_core_add_rejects_string_argv(self):
        sup = core.Supervisor(self.base / 'core')
        self.addCleanup(sup.close)
        for bad in ('notlist', [], [''], [1], ['a'] * 2000):
            with self.assertRaises(ValueError):
                sup.add('n', bad, str(self.root))

    def test_worker_run_once_survives_a_malformed_row(self):
        w = worker.WorkerSupervisor(self.base / 'wk')
        self.addCleanup(w.close)
        for raw in ('not json', 'null', '123', '[]', '"astring"'):
            w.db.execute("INSERT INTO jobs(label,argv,cwd,max_attempts,updated,state) VALUES(?,?,?,?,?, 'pending')",
                         ('bad', raw, str(self.root), 2, time.time()))
            w.db.commit()
            result = w.run_once(timeout=10)      # must not raise
            self.assertEqual(result['state'], 'failed')


class LockTests(unittest.TestCase):
    def test_lock_path_that_is_a_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.adm-repair.lock').mkdir()
            with self.assertRaises(SafetyError):
                with exclusive_project(root):
                    pass

    def test_second_builder_is_refused_while_the_lock_is_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            home = base / 'home'; home.mkdir()
            ans = {'title': 'T', 'summary': 's', 'features': ['f'], 'tests': ['t'],
                   'needs_internet': False, 'questions': []}
            plan = intake.approve(intake.create_plan(base / 'state', 'a small locked tool', mode='new', folder='',
                                  generator=lambda m, p, t: ans, model='ollama/x', home=home)['path'])
            with exclusive_project(Path(plan['folder'])):          # hold the lock
                with self.assertRaises(SafetyError):
                    build.build_from_plan(plan['path'], base / 'ev',
                                          test_generator=lambda *a, **k: {'files': [{'path': 'test_app.py',
                                              'content': 'import app\ndef test():\n assert 1\n'}]},
                                          code_generator=lambda *a, **k: {'files': [{'path': 'app.py', 'content': 'x=1'}]},
                                          model='ollama/x', runner=None, require_sandbox=False)


class JournalAndStatusTests(unittest.TestCase):
    def test_recover_journal_rejects_malformed_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ev = base / 'ev'; ev.mkdir()
            for bad in ('not json', 'null', '[1,2]', '{}', '{"version":1,"root":"x","entries":[1]}'):
                (ev / 'repair-journal.json').write_text(bad)
                with self.assertRaises(SafetyError):
                    repair_recovery.recover_journal(base, ev)

    def test_read_status_tolerates_a_corrupt_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = Path(tmp)
            for bad in ('not json', '[]', 'null', '"x"', '{bad'):
                (st / 'daemon-status.json').write_text(bad)
                self.assertEqual(daemon.read_status(st)['state'], 'unknown')


if __name__ == '__main__':
    unittest.main()
