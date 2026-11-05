"""Regression tests for adversarial round 6: release/archive, provisioning, pipeline guards."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from adm import release, provision, pipeline
from adm.engine import SafetyError


def _zip(entries: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return buf.getvalue()


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def _check(self, data):
        p = self.base / 't.zip'
        p.write_bytes(data)
        with self.assertRaises(ValueError):
            release.verify_source_release(p)

    def test_rejects_non_zip_and_malformed_manifests(self):
        for data in (b'not a zip', _zip({}), _zip({'ADM/SOURCE-MANIFEST.json': 'not json'}),
                     _zip({'ADM/SOURCE-MANIFEST.json': '[]'}),
                     _zip({'ADM/SOURCE-MANIFEST.json': '{"files": {"../evil.py": "x"}}', 'ADM/../evil.py': 'x'})):
            self._check(data)

    def test_rejects_a_zip_bomb_before_reading_it(self):
        # tiny compressed, ~80MB uncompressed: must be refused by the size guard, not read into memory
        self._check(_zip({'ADM/SOURCE-MANIFEST.json': '{"files": {"big.py": "00"}}',
                          'ADM/big.py': 'A' * (80 * 1024 * 1024)}))


class ProvisionTests(unittest.TestCase):
    def test_requires_approval_and_validates_the_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            j = Path(tmp) / 'j.json'
            with self.assertRaises(PermissionError):
                provision.execute_plan({'platform': 'Windows', 'steps': []}, j)
            for bad in (None, {}, {'platform': 'Linux'}, {'platform': 'Windows', 'steps': 'x'},
                        {'platform': 'Windows', 'steps': [{'key': 'evil'}]}):
                with self.assertRaises((ValueError, SafetyError)):
                    provision.execute_plan(bad, j, approved=True, executor=lambda s: {'status': 'ok'})


class PipelineTests(unittest.TestCase):
    def test_missing_or_malformed_spec_is_a_clean_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            with self.assertRaises(SafetyError):
                pipeline.run_pipeline(state, timeout=5)        # no pipeline.json
            (state / 'pipeline.json').write_text('not json')
            with self.assertRaises(SafetyError):
                pipeline.run_pipeline(state, timeout=5)
            (state / 'pipeline.json').write_text('[]')
            with self.assertRaises(SafetyError):
                pipeline.run_pipeline(state, timeout=5)


if __name__ == '__main__':
    unittest.main()
