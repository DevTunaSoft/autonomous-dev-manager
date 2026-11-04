"""Regression resume must never reuse absent, altered, or legacy evidence."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from adm.regression import run_suite


class EvidenceResumeTests(unittest.TestCase):
    def fixture(self, root):
        (root / 'tests').mkdir()
        marker = root / 'executions.txt'
        (root / 'tests' / 'test_one.py').write_text(
            'import unittest\nfrom pathlib import Path\n'
            'class T(unittest.TestCase):\n'
            ' def test_one(self):\n'
            f'  p=Path({str(marker)!r});p.write_text(p.read_text()+"x" if p.exists() else "x")\n')
        return marker

    def test_untouched_evidence_is_reused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); marker=self.fixture(root); checkpoint=root/'progress.json'
            first=run_suite(root, progress_path=checkpoint)
            self.assertTrue(first['passed'])
            self.assertEqual(len(first['modules'][0]['log_sha256']),64)
            second=run_suite(root,progress_path=checkpoint,resume=True)
            self.assertTrue(second['passed'])
            self.assertTrue(second['modules'][0]['resumed'])
            self.assertEqual(marker.read_text(),'x')

    def test_modified_log_forces_rerun(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); marker=self.fixture(root); checkpoint=root/'progress.json'
            first=run_suite(root,progress_path=checkpoint)
            Path(first['modules'][0]['log_path']).write_text('tampered')
            second=run_suite(root,progress_path=checkpoint,resume=True)
            self.assertTrue(second['passed'])
            self.assertFalse(second['modules'][0].get('resumed',False))
            self.assertEqual(marker.read_text(),'xx')

    def test_missing_log_forces_rerun(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); marker=self.fixture(root); checkpoint=root/'progress.json'
            first=run_suite(root,progress_path=checkpoint)
            Path(first['modules'][0]['log_path']).unlink()
            second=run_suite(root,progress_path=checkpoint,resume=True)
            self.assertTrue(second['passed'])
            self.assertEqual(marker.read_text(),'xx')

    def test_legacy_checkpoint_without_hash_forces_rerun(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); marker=self.fixture(root); checkpoint=root/'progress.json'
            run_suite(root,progress_path=checkpoint)
            data=json.loads(checkpoint.read_text());del data['modules'][0]['log_sha256']
            checkpoint.write_text(json.dumps(data))
            second=run_suite(root,progress_path=checkpoint,resume=True)
            self.assertTrue(second['passed'])
            self.assertEqual(marker.read_text(),'xx')

    def test_python_interpreter_change_rejects_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); self.fixture(root); checkpoint=root/'progress.json'
            run_suite(root,progress_path=checkpoint)
            with self.assertRaisesRegex(ValueError,'Source changed'):
                run_suite(root,progress_path=checkpoint,resume=True,python='/different/python')
