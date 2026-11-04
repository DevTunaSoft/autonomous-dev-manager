import json
import sys
import tempfile
import unittest
from pathlib import Path
from adm.agent import (agent_repair_proof, protected_hashes, safe_local_model,
                       validate_project)
from adm.engine import SafetyError, make_broken_demo


class AgentProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.project = make_broken_demo(self.base / 'project')
        self.evidence = self.base / 'evidence'

    def tearDown(self):
        self.temp.cleanup()

    def fake_agent(self, body):
        path = self.base / 'fake_agent.py'
        path.write_text('import pathlib,sys\n' + body + '\n', encoding='utf-8')
        return [sys.executable, str(path)]

    def test_real_test_failure_fake_agent_repair(self):
        fake = self.fake_agent("assert sys.argv[1]=='run'\nassert '--model' in sys.argv\n"
                               "pathlib.Path('calculator.py').write_text('def add(a,b):\\n    return a + b\\n')")
        report = agent_repair_proof(self.project, self.evidence, agent_executable=fake)
        self.assertEqual(report['status'], 'verified_agent_repair')
        self.assertNotEqual(report['baseline']['exit_code'], 0)
        self.assertEqual(report['attempts'][0]['test']['exit_code'], 0)
        self.assertTrue(report['attempts'][0]['source_changed'])
        self.assertTrue(report['attempts'][0]['protected_unchanged'])
        self.assertTrue((self.evidence / 'agent-proof-report.json').is_file())

    def test_failed_repair_cannot_pass(self):
        fake = self.fake_agent('print("I fixed it")')
        report = agent_repair_proof(self.project, self.evidence, agent_executable=fake,
                                    max_repairs=2)
        self.assertEqual(report['status'], 'repair_failed')
        self.assertEqual(len(report['attempts']), 2)

    def test_modified_test_is_blocked_even_if_tests_pass(self):
        fake = self.fake_agent("pathlib.Path('test_calculator.py').write_text('import unittest\\n')\n"
                               "pathlib.Path('calculator.py').write_text('def add(a,b):\\n    return a + b\\n')")
        report = agent_repair_proof(self.project, self.evidence, agent_executable=fake)
        self.assertEqual(report['status'], 'blocked_protected_files_modified')

    def test_local_only_model_guard(self):
        for invalid in ('', 'anthropic/model', 'openai/gpt', 'ollama/', 'ollama/foo model', 'ollama/x;bad'):
            with self.subTest(invalid=invalid), self.assertRaises(SafetyError):
                safe_local_model(invalid)
        self.assertEqual(safe_local_model('ollama/qwen2.5-coder:3b'), 'ollama/qwen2.5-coder:3b')

    def test_symlink_project_rejected(self):
        try:
            (self.project / 'other.py').symlink_to(self.base / 'other.py')
        except (OSError, NotImplementedError):
            self.skipTest('Symlinks unavailable')
        with self.assertRaises(SafetyError):
            validate_project(self.project, self.evidence)

    def test_interrupted_before_agent_can_resume(self):
        fake = self.fake_agent("pathlib.Path('calculator.py').write_text('def add(a,b):\\n    return a + b\\n')")
        interrupted = agent_repair_proof(self.project, self.evidence,
                                         agent_executable=fake, interrupt_after_baseline=True)
        self.assertEqual(interrupted['status'], 'baseline_failed')
        final = agent_repair_proof(self.project, self.evidence, agent_executable=fake)
        self.assertEqual(final['status'], 'verified_agent_repair')

    def test_ambiguous_interrupted_agent_is_not_replayed(self):
        fake = self.fake_agent('print("noop")')
        agent_repair_proof(self.project, self.evidence, agent_executable=fake,
                           interrupt_after_baseline=True)
        report_path = self.evidence / 'agent-proof-report.json'
        report = json.loads(report_path.read_text(encoding='utf-8'))
        report['status'] = 'agent_in_flight'
        report_path.write_text(json.dumps(report), encoding='utf-8')
        with self.assertRaises(SafetyError):
            agent_repair_proof(self.project, self.evidence, agent_executable=fake)

    def test_wrong_model_checkpoint_rejected(self):
        fake = self.fake_agent('print("hello")')
        agent_repair_proof(self.project, self.evidence, agent_executable=fake, max_repairs=1)
        with self.assertRaises(SafetyError):
            agent_repair_proof(self.project, self.evidence, model='ollama/other:3b',
                               agent_executable=fake)

    def test_workspace_requirement(self):
        with self.assertRaises(SafetyError):
            validate_project(self.project, self.project / 'evidence')

    def test_no_agent_missing_is_clear(self):
        fake = self.fake_agent("print('ignored')")
        # Inject a non-existent executable, verify captured error and no success.
        report = agent_repair_proof(self.project, self.evidence,
                                    agent_executable=['a-really-unlikely-executable-ADM-003'],
                                    max_repairs=1)
        self.assertEqual(report['status'], 'repair_failed')
        self.assertEqual(report['attempts'][0]['agent']['exit_code'], 127)

if __name__ == '__main__':
    unittest.main()
