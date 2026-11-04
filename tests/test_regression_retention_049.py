import json, os, tempfile, textwrap, time, unittest
from pathlib import Path
from adm.regression import prune_logs, run_suite


def _mkrun(parent, name, age):
    d = Path(parent) / name
    d.mkdir()
    (d / 'x.log').write_text('x')
    t = time.time() - age
    os.utime(d, (t, t))
    return d


class RetentionTests(unittest.TestCase):
    def test_prunes_oldest_but_keeps_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = _mkrun(tmp, 'regression-run-a', 300)
            mid = _mkrun(tmp, 'regression-run-b', 200)
            new = _mkrun(tmp, 'regression-run-c', 100)
            removed = prune_logs(Path(tmp), 1, {old / 'x.log'})
            self.assertEqual(removed, ['regression-run-b'])
            self.assertTrue(old.exists() and new.exists() and not mid.exists())

    def test_rejects_invalid_keep(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                prune_logs(Path(tmp), 0)

    def test_non_run_directories_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp) / 'keepme'
            other.mkdir()
            _mkrun(tmp, 'regression-run-a', 10)
            prune_logs(Path(tmp), 1)
            self.assertTrue(other.exists())

    def test_suite_records_environment_and_prunes_without_losing_current_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'proj'
            (root / 'tests').mkdir(parents=True)
            (root / 'tests' / 'test_ok.py').write_text(textwrap.dedent('''
                import unittest
                class T(unittest.TestCase):
                    def test_a(self): self.assertTrue(True)
            '''))
            out = Path(tmp) / 'logs' / 'r.json'
            first = run_suite(root, timeout_per_module=30, progress_path=out)
            second = run_suite(root, timeout_per_module=30, progress_path=out, keep_runs=1)
            self.assertTrue(second['passed'])
            self.assertIn('python_version', second['environment'])
            self.assertEqual(len(second['pruned_runs']), 1)
            self.assertTrue(Path(second['modules'][0]['log_path']).is_file())
            self.assertEqual(len(list(out.parent.glob('regression-run-*'))), 1)

if __name__ == '__main__':
    unittest.main()
