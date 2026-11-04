"""Independent regression invocations cannot clobber diagnostic evidence."""
import concurrent.futures
import tempfile
import unittest
from pathlib import Path
from adm.regression import run_suite, _file_sha256

class RegressionLogIsolationTests(unittest.TestCase):
    def test_sequential_runs_have_distinct_immutable_log_paths(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'tests').mkdir()
            (root/'tests'/'test_sample.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')
            a=run_suite(root, progress_path=root/'one.json')
            path=Path(a['modules'][0]['log_path']); digest=a['modules'][0]['log_sha256']
            b=run_suite(root, progress_path=root/'two.json')
            self.assertTrue(a['passed'] and b['passed'])
            self.assertNotEqual(path, Path(b['modules'][0]['log_path']))
            self.assertEqual(_file_sha256(path), digest)

    def test_simultaneous_runs_keep_separate_logs(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'tests').mkdir()
            (root/'tests'/'test_sample.py').write_text('import unittest\nimport time\nclass T(unittest.TestCase):\n def test_ok(self): time.sleep(0.2); self.assertTrue(True)\n')
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                a_future=pool.submit(run_suite,root,progress_path=root/'one.json')
                b_future=pool.submit(run_suite,root,progress_path=root/'two.json')
                a,b=a_future.result(),b_future.result()
            self.assertTrue(a['passed'] and b['passed'])
            self.assertNotEqual(a['modules'][0]['log_path'],b['modules'][0]['log_path'])
            for result in (a,b):
                entry=result['modules'][0]
                self.assertEqual(_file_sha256(Path(entry['log_path'])),entry['log_sha256'])
