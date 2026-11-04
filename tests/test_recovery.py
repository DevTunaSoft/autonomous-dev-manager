import json
import sys
import tempfile
import unittest
from pathlib import Path
from adm.agent import agent_repair_proof
from adm.engine import SafetyError, make_broken_demo
from adm.preflight import local_preflight
from adm.recovery import inventory, restore_snapshot, save_snapshot

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = make_broken_demo(self.base/'project')
        self.evidence = self.base/'evidence'

    def fake(self, source):
        path = self.base/'fake.py'
        path.write_text(source, encoding='utf-8')
        return [sys.executable, str(path)]

    def test_snapshot_reverts_added_changed_deleted(self):
        snapshot = self.base/'backup'
        expected = save_snapshot(self.root, snapshot)
        (self.root/'calculator.py').write_text('broken')
        (self.root/'test_calculator.py').unlink()
        (self.root/'unexpected.txt').write_text('new')
        restore_snapshot(self.root, snapshot, expected)
        self.assertEqual(inventory(self.root), expected)
        self.assertFalse((self.root/'unexpected.txt').exists())

    def test_damaged_snapshot_is_rejected(self):
        expected = save_snapshot(self.root, self.base/'backup')
        (self.base/'backup'/'calculator.py').write_text('tampered')
        with self.assertRaises(SafetyError):
            restore_snapshot(self.root, self.base/'backup', expected)

    def test_auto_recover_interrupted_agent_and_complete(self):
        good = self.fake("from pathlib import Path\nPath('calculator.py').write_text('def add(a,b):\\n    return a + b\\n')")
        agent_repair_proof(self.root, self.evidence, agent_executable=good, interrupt_after_baseline=True)
        # Simulate a crash AFTER the worker partially edits code.
        before = save_snapshot(self.root, self.evidence/'snapshots'/'1')
        (self.root/'calculator.py').write_text('def nope(): pass\n')
        report_file = self.evidence/'agent-proof-report.json'
        state = json.loads(report_file.read_text())
        state['status'] = 'agent_in_flight'
        state['active_checkpoint'] = {'number': 1, 'hashes': before}
        report_file.write_text(json.dumps(state))
        report = agent_repair_proof(self.root, self.evidence, agent_executable=good)
        self.assertEqual(report['status'], 'verified_agent_repair')
        self.assertEqual(report['recoveries'], 1)

    def test_no_checkpoint_still_refuses_uncertain_state(self):
        fake = self.fake('print(0)')
        agent_repair_proof(self.root, self.evidence, agent_executable=fake, interrupt_after_baseline=True)
        state_file = self.evidence/'agent-proof-report.json'
        state = json.loads(state_file.read_text())
        state['status'] = 'agent_in_flight'
        state_file.write_text(json.dumps(state))
        with self.assertRaises(SafetyError):
            agent_repair_proof(self.root, self.evidence, agent_executable=fake)

    def test_reject_symlink_on_snapshot(self):
        try: (self.root/'escape').symlink_to(self.base)
        except (OSError, NotImplementedError): self.skipTest('Symlinks unavailable')
        with self.assertRaises(SafetyError):
            save_snapshot(self.root, self.base/'backup')

    def test_preflight_reports_unavailable_services_without_crashing(self):
        result = local_preflight()
        self.assertIn('ready', result)
        self.assertIn('opencode', result)
        self.assertIn('ollama', result)
        self.assertIsInstance(result['problems'], list)

    def test_preflight_refuses_external_endpoint(self):
        with self.assertRaises(ValueError):
            local_preflight(endpoint='https://example.com')

if __name__ == '__main__': unittest.main()
