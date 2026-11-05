import tempfile
import unittest
from pathlib import Path
from adm.engine import SafetyError
from adm.live_acceptance import run_live_acceptance, main

class LiveAcceptanceTests(unittest.TestCase):
    def test_refuses_missing_model_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'new'
            with self.assertRaises(SafetyError):
                run_live_acceptance(dest, health=lambda: {'reachable': True, 'installed_models': []})
            self.assertFalse(dest.exists())

    def test_refuses_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'out'
            dest.mkdir()
            (dest / 'keep.txt').write_text('keep')
            with self.assertRaises(SafetyError):
                run_live_acceptance(dest, health=lambda: {'reachable': True, 'installed_models': ['qwen2.5-coder:3b']})
            self.assertEqual((dest / 'keep.txt').read_text(), 'keep')

    def test_fake_repair_cannot_claim_real_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fake_repair(root, evidence, **kwargs):
                return {'status': 'verified_direct_repair', 'live_model_verified': True, 'network_generator': False,
                        'baseline': {'exit_code': 1}, 'attempts': [{'passed': True, 'test': {'exit_code': 0}}]}
            result = run_live_acceptance(Path(tmp) / 'out',
                health=lambda: {'reachable': True, 'installed_models': ['qwen2.5-coder:3b']},
                repair=fake_repair)
            self.assertFalse(result['passed'])
            self.assertFalse(result['real_model_verified'])

    def test_cli_requires_explicit_unsafe_execution_acknowledgement(self):
        with self.assertRaises(SystemExit) as caught:
            main(['--output', '/tmp/not-executed'])
        self.assertEqual(caught.exception.code, 2)

if __name__ == '__main__':
    unittest.main()
