import json
import tempfile
import unittest
from pathlib import Path
from adm.provision import execute_plan
from adm.setup import build_plan

GIB = 1024**3
HW = {'ram_available_bytes': 12*GIB, 'disk_free_bytes': 80*GIB}

class ProvisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'setup.json'
        self.plan = build_plan(system='Windows', binaries={'winget':'winget'}, hardware=HW)
        self.calls = []
    def execute(self, step, **kwargs):
        self.calls.append(step['key'])
        return {'key':step['key'], 'status':'completed'}
    def test_consent_required(self):
        with self.assertRaises(PermissionError):
            execute_plan(self.plan, self.path, executor=self.execute)
        self.assertFalse(self.path.exists())
    def test_dependency_order(self):
        state = execute_plan(self.plan, self.path, approved=True, executor=self.execute)
        self.assertEqual(self.calls, ['install_ollama', 'pull_model'])
        self.assertEqual(state['status'], 'blocked') # OpenCode still missing
        self.assertEqual(json.loads(self.path.read_text())['results']['pull_model']['status'], 'completed')
    def test_failure_stops_before_model_pull(self):
        def fail(step, **kwargs):
            self.calls.append(step['key'])
            return {'status':'failed'}
        state = execute_plan(self.plan, self.path, approved=True, executor=fail)
        self.assertEqual(self.calls, ['install_ollama'])
        self.assertNotIn('pull_model', state['results'])
    def test_resume_verifies_previous_steps(self):
        execute_plan(self.plan, self.path, approved=True, executor=self.execute)
        self.calls.clear()
        execute_plan(self.plan, self.path, approved=True, executor=self.execute, verify=lambda key: True)
        self.assertEqual(self.calls, [])
    def test_resume_rechecks_when_not_verified(self):
        execute_plan(self.plan, self.path, approved=True, executor=self.execute)
        self.calls.clear()
        execute_plan(self.plan, self.path, approved=True, executor=self.execute, verify=lambda key: False)
        self.assertEqual(self.calls, ['install_ollama','pull_model'])
    def test_changed_plan_rejected(self):
        execute_plan(self.plan, self.path, approved=True, executor=self.execute)
        altered = build_plan(system='Windows', binaries={'winget':'winget'}, hardware=HW, model='qwen2.5-coder:1.5b')
        with self.assertRaises(ValueError):
            execute_plan(altered, self.path, approved=True, executor=self.execute)
    def test_non_windows_rejected(self):
        with self.assertRaises(ValueError):
            execute_plan(build_plan(system='Linux', binaries={}, hardware=HW), self.path, approved=True, executor=self.execute)
    def test_duplicate_step_rejected(self):
        self.plan['steps'].append(dict(self.plan['steps'][0]))
        with self.assertRaises(ValueError):
            execute_plan(self.plan, self.path, approved=True, executor=self.execute)

    def test_corrupt_journal_with_nondict_result_value_rejected(self):
        # A tampered resume journal whose results value is not a dict must raise
        # ValueError, never AttributeError on .get().
        fp = json.dumps(self.plan['steps'], sort_keys=True)
        for bad in ('{"results": {"install_ollama": "notadict"}, "fingerprint": %s}' % json.dumps(fp),
                    '{"results": {"install_ollama": 123}, "fingerprint": %s}' % json.dumps(fp),
                    '{"results": {"install_ollama": null}, "fingerprint": %s}' % json.dumps(fp)):
            self.path.write_text(bad, encoding='utf-8')
            with self.assertRaises(ValueError):
                execute_plan(self.plan, self.path, approved=True, executor=self.execute)

if __name__ == '__main__': unittest.main()
