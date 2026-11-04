import json
from pathlib import Path
import tempfile
import unittest
from adm.acceptance import run_offline_acceptance
from adm.engine import SafetyError


class AcceptanceTests(unittest.TestCase):
    def test_real_http_and_real_tests_with_fake_ai(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_offline_acceptance(Path(tmp) / 'trial')
            self.assertTrue(result['passed'])
            self.assertFalse(result['real_model_verified'])
            self.assertEqual(result['requests_seen'], 1)
            self.assertNotEqual(result['baseline_exit'], 0)
            self.assertEqual(result['post_repair_exit'], 0)
            self.assertEqual(json.loads((Path(tmp) / 'trial' / 'acceptance-summary.json').read_text()), result)

    def test_does_not_overwrite_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'existing.txt').write_text('keep')
            with self.assertRaises(SafetyError):
                run_offline_acceptance(folder)
            self.assertEqual((folder / 'existing.txt').read_text(), 'keep')
