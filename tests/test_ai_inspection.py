import json
from pathlib import Path
import tempfile
import unittest
from adm.queued_ai import enqueue_repair, inspect_repair
from adm.worker import WorkerSupervisor
from adm.engine import SafetyError

class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        b = Path(self.temp.name)
        self.root, self.state, self.evidence = b/'project', b/'state', b/'evidence'
        self.root.mkdir()
        (self.root/'requirements.json').write_text('{"goal":"add"}')
        (self.root/'app.py').write_text('def add(a,b): return a-b\n')
        (self.root/'test_app.py').write_text('import unittest\n')
        self.job = enqueue_repair(self.state,self.root,self.evidence)

    def update(self, state, exit_code=None):
        w = WorkerSupervisor(self.state)
        try:
            w.db.execute('UPDATE jobs SET state=?,exit_code=? WHERE id=?',
                         (state,exit_code,self.job['job_id']))
        finally:
            w.close()

    def report(self, status):
        p=Path(self.job['evidence']);p.mkdir(parents=True,exist_ok=True)
        (p/'ollama-direct-report.json').write_text(json.dumps({'status':status}))

    def inspect(self):
        return inspect_repair(self.state,self.job['job_id'])

    def test_pending_is_not_verified(self):
        self.assertEqual(self.inspect()['status'],'in_progress')
        self.assertFalse(self.inspect()['verified'])

    def test_worker_pass_without_report_is_not_verified(self):
        self.update('passed',0)
        self.assertEqual(self.inspect()['status'],'evidence_mismatch')

    def test_worker_pass_and_success_report(self):
        self.update('passed',0);self.report('verified_direct_repair')
        self.assertTrue(self.inspect()['verified'])

    def test_report_success_worker_failure_is_not_verified(self):
        self.update('failed',1);self.report('verified_direct_repair')
        self.assertFalse(self.inspect()['verified'])

    def test_unresolved_journal_overrides_success(self):
        self.update('passed',0);self.report('verified_direct_repair')
        (Path(self.job['evidence'])/'repair-journal.json').write_text('{}')
        self.assertEqual(self.inspect()['status'],'recovery_required')

    def test_invalid_json_is_fail_closed(self):
        self.update('passed',0)
        p=Path(self.job['evidence']);p.mkdir(parents=True,exist_ok=True)
        (p/'ollama-direct-report.json').write_text('{')
        self.assertEqual(self.inspect()['status'],'invalid_evidence')

    def test_unknown_job_refused(self):
        with self.assertRaises(SafetyError): inspect_repair(self.state,999)
