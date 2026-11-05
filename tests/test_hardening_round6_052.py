"""Regression tests for adversarial round 6: release ZIP, admission math, first-run assessment."""
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from adm import release, adaptive, firstrun


def _zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        for name, data in entries:
            z.writestr(name, data)
    return buf.getvalue()


class ReleaseVerifyTests(unittest.TestCase):
    def test_malformed_archives_raise_valueerror(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cases = [
                [],                                                           # empty, no manifest
                [('ADM/app.py', 'x=1')],                                      # no manifest
                [('ADM/SOURCE-MANIFEST.json', 'not json')],
                [('ADM/SOURCE-MANIFEST.json', '[1,2,3]')],                    # not a dict
                [('ADM/SOURCE-MANIFEST.json', '{"x":1}')],                    # no files key
                [('ADM/SOURCE-MANIFEST.json', '{"files":"nope"}')],           # files not dict
                [('ADM/SOURCE-MANIFEST.json', '{"files":{"a.py":123}}')],     # bad value type
                [('ADM/SOURCE-MANIFEST.json', '{"files":{"../x.py":"0"}}')],  # traversal
            ]
            for i, entries in enumerate(cases):
                p = base / f'c{i}.zip'
                p.write_bytes(_zip(entries))
                with self.assertRaises(ValueError, msg=str(entries)[:60]):
                    release.verify_source_release(p)
            notzip = base / 'n.zip'
            notzip.write_bytes(b'not a zip')
            with self.assertRaises(ValueError):
                release.verify_source_release(notzip)


class AdmissionTests(unittest.TestCase):
    def test_adversarial_snapshots_do_not_crash(self):
        for snap in [{}, {'ram_available_bytes': 'lots', 'disk_free_bytes': 10},
                     {'ram_available_bytes': float('nan'), 'disk_free_bytes': float('nan')},
                     {'ram_available_bytes': float('inf'), 'disk_free_bytes': float('inf'), 'cpu_count': 'x'},
                     {'ram_available_bytes': -5, 'disk_free_bytes': -5}]:
            d = adaptive.decide(snap, job_ram_gib=2)
            self.assertFalse(d.allowed)          # all malformed/insufficient -> not allowed, no crash

    def test_invalid_params_raise(self):
        good = {'ram_available_bytes': 16 * 1024**3, 'disk_free_bytes': 100 * 1024**3, 'cpu_count': 8}
        for kwargs in [{'job_ram_gib': float('nan')}, {'job_ram_gib': 'x'}, {'job_ram_gib': -1},
                       {'job_ram_gib': 2, 'job_disk_gib': float('inf')}]:
            with self.assertRaises(ValueError):
                adaptive.decide(good, **kwargs)

    def test_a_healthy_machine_is_still_admitted(self):
        d = adaptive.decide({'ram_available_bytes': 16 * 1024**3, 'disk_free_bytes': 100 * 1024**3, 'cpu_count': 8},
                            job_ram_gib=2)
        self.assertTrue(d.allowed)


class AssessTests(unittest.TestCase):
    def test_broken_exe_finder_does_not_abort_assessment(self):
        def boom(name):
            raise OSError('discovery blew up')
        result = firstrun.assess(ram_gib=16, find_exe=boom)
        self.assertIsInstance(result, dict)
        self.assertIn('ready', result)


if __name__ == '__main__':
    unittest.main()
