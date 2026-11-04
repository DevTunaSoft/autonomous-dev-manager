import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adm.engine import make_broken_demo, SafetyError
from adm.pipeline import start_pipeline, run_pipeline
from adm.worker import WorkerSupervisor


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / 'project'
        make_broken_demo(self.project)
        self.state = self.base / 'state'
        self.evidence = self.base / 'evidence'

    def test_prepare_persists_and_is_idempotent(self):
        a = start_pipeline(self.state, self.project, self.evidence)
        b = start_pipeline(self.state, self.project, self.evidence)
        self.assertEqual(a, b)
        sup = WorkerSupervisor(self.state / 'workers')
        try:
            self.assertEqual(len(sup.status()), 1)
            self.assertEqual(sup.status()[0]['state'], 'pending')
        finally:
            sup.close()

    def test_rejects_changed_spec(self):
        start_pipeline(self.state, self.project, self.evidence)
        with self.assertRaises(SafetyError):
            start_pipeline(self.state, self.project, self.evidence, model='ollama/other:3b')

    def test_no_paid_models(self):
        with self.assertRaises(SafetyError):
            start_pipeline(self.state, self.project, self.evidence, model='openai/gpt')

    def test_overlapping_state_rejected(self):
        with self.assertRaises(SafetyError):
            start_pipeline(self.project / '.adm', self.project, self.evidence)

    def test_missing_local_agent_is_not_success(self):
        start_pipeline(self.state, self.project, self.evidence)
        result = run_pipeline(self.state, timeout=15)
        self.assertEqual(result['status'], 'not_verified')
        self.assertEqual(result['worker']['state'], 'failed')

    def test_worker_exit_alone_never_proves_success(self):
        start_pipeline(self.state, self.project, self.evidence)
        sup = WorkerSupervisor(self.state / 'workers')
        try:
            sup.db.execute("UPDATE jobs SET state='passed',exit_code=0 WHERE id=1")
        finally:
            sup.close()
        self.assertEqual(run_pipeline(self.state)['status'], 'not_verified')

    def test_protected_file_change_rejects_fake_evidence(self):
        start_pipeline(self.state, self.project, self.evidence)
        spec = json.loads((self.state / 'pipeline.json').read_text())
        self.evidence.mkdir()
        (self.evidence / 'agent-proof-report.json').write_text(json.dumps({
            'status': 'verified_agent_repair', 'project': str(self.project.resolve()),
            'model': spec['model'], 'protected_before': spec['protected'],
            'attempts': [{'test': {'exit_code': 0}, 'protected_unchanged': True, 'source_changed': True}]}))
        (self.project / 'requirements.json').write_text('{}')
        sup = WorkerSupervisor(self.state / 'workers')
        try:
            sup.db.execute("UPDATE jobs SET state='passed',exit_code=0 WHERE id=1")
        finally:
            sup.close()
        self.assertEqual(run_pipeline(self.state)['status'], 'not_verified')

if __name__ == '__main__':
    unittest.main()

class RealProcessIntegrationTests(unittest.TestCase):
    """Executes real supervisor + real subprocess + fake agent, not a live LLM."""
    @unittest.skipUnless(__import__('os').name == 'posix', 'POSIX fake agent executable')
    def test_supervised_agent_process_end_to_end(self):
        import os
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            project = base / 'project'
            make_broken_demo(project)
            binary = base / 'bin'
            binary.mkdir()
            fake = binary / 'opencode'
            fake.write_text('#!' + __import__('sys').executable + '\n'
                            'from pathlib import Path\n'
                            'Path("calculator.py").write_text("def add(a,b):\\n    return a + b\\n")\n')
            fake.chmod(0o755)
            state, evidence = base / 'state', base / 'evidence'
            start_pipeline(state, project, evidence)
            old = os.environ.get('PATH', '')
            try:
                os.environ['PATH'] = str(binary) + os.pathsep + old
                result = run_pipeline(state, timeout=25)
            finally:
                os.environ['PATH'] = old
            self.assertEqual(result['status'], 'verified', result)
            self.assertEqual(result['worker']['state'], 'passed')
            self.assertEqual(json.loads((evidence/'agent-proof-report.json').read_text())['status'],
                             'verified_agent_repair')
