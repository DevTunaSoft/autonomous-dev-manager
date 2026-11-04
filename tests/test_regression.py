import tempfile
from pathlib import Path
import unittest
from adm.regression import run_suite

class RegressionRunnerTests(unittest.TestCase):
    def test_reject_missing_tests(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'No test modules'):
                run_suite(Path(temp))

    def test_reject_invalid_timeout(self):
        with self.assertRaises(ValueError):
            run_suite(Path('.'), timeout_per_module=0)

    def test_passing_module(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'tests').mkdir()
            (root / 'tests' / 'test_ok.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')
            result = run_suite(root, timeout_per_module=10)
            self.assertTrue(result['passed'])
            self.assertEqual(result['total_tests'], 1)

    def test_failure_is_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'tests').mkdir()
            (root / 'tests' / 'test_fail.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_fail(self): self.fail("intentional")\n')
            result = run_suite(root, timeout_per_module=10)
            self.assertFalse(result['passed'])
            self.assertEqual(result['modules'][0]['status'], 'failed')

    def test_timeout_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'tests').mkdir()
            (root / 'tests' / 'test_slow.py').write_text('import time\nimport unittest\nclass T(unittest.TestCase):\n def test_slow(self): time.sleep(4)\n')
            result = run_suite(root, timeout_per_module=1)
            self.assertFalse(result['passed'])
            self.assertEqual(result['modules'][0]['status'], 'timeout')

class RegressionProcessTreeTests(unittest.TestCase):
    @unittest.skipUnless(__import__('os').name == 'posix', 'POSIX process groups')
    def test_timeout_stops_descendant_process(self):
        import os
        import time
        from adm.worker import pid_alive
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'tests').mkdir()
            pid_file = root / 'child.pid'
            (root / 'tests' / 'test_hanging.py').write_text(
                'import subprocess,sys,time,unittest\n'
                'class T(unittest.TestCase):\n'
                ' def test_hang(self):\n'
                '  p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"])\n'
                f'  open({str(pid_file)!r},"w").write(str(p.pid))\n'
                '  time.sleep(30)\n', encoding='utf-8')
            result = run_suite(root, timeout_per_module=1)
            self.assertEqual(result['modules'][0]['status'], 'timeout')
            self.assertTrue(pid_file.exists())
            for _ in range(30):
                if not pid_alive(int(pid_file.read_text())):
                    break
                time.sleep(.1)
            self.assertFalse(pid_alive(int(pid_file.read_text())))

class RegressionCheckpointTests(unittest.TestCase):
    def test_partial_progress_is_persisted_before_hanging_module(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'tests').mkdir()
            (root/'tests'/'test_a.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n')
            (root/'tests'/'test_b.py').write_text('import unittest,time\nclass T(unittest.TestCase):\n def test_hang(self): time.sleep(20)\n')
            path = root/'progress.json'
            events = []
            report = run_suite(root, timeout_per_module=4, progress_path=path,
                               on_progress=lambda name,state: events.append((name,state)))
            saved = json.loads(path.read_text())
            self.assertEqual(saved, report)
            self.assertEqual([m['status'] for m in saved['modules']], ['passed','timeout'])
            self.assertEqual(saved['total_tests'], 1)
            self.assertIsNone(saved['running'])
            self.assertIn(('test_b.py','started'),events)
            self.assertFalse(saved['passed'])

    def test_checkpoint_does_not_leave_temporary_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'tests').mkdir()
            (root/'tests'/'test_ok.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n')
            path = root/'progress.json'
            self.assertTrue(run_suite(root, timeout_per_module=10, progress_path=path)['passed'])
            self.assertEqual(list(root.glob('.regression-*.json')), [])

class RegressionBudgetTests(unittest.TestCase):
    def test_selected_module_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'tests').mkdir()
            (root/'tests'/'test_ok.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n')
            (root/'tests'/'test_bad.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_bad(self): self.fail()\n')
            result=run_suite(root, selected_modules={'test_ok.py'}, timeout_per_module=10)
            self.assertTrue(result['passed']); self.assertEqual(len(result['modules']),1)
    def test_total_budget_marks_unrun_not_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'tests').mkdir()
            (root/'tests'/'test_a.py').write_text('import time,unittest\nclass T(unittest.TestCase):\n def test_slow(self): time.sleep(2)\n')
            (root/'tests'/'test_b.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n')
            result=run_suite(root,timeout_per_module=10,max_total_seconds=.5)
            self.assertFalse(result['passed'])
            self.assertEqual([m['status'] for m in result['modules']],['timeout','not_run_budget'])
    def test_invalid_total_budget(self):
        with self.assertRaises(ValueError):
            run_suite(Path('.'), max_total_seconds=0)

class RegressionEvidenceTests(unittest.TestCase):
    def test_failing_test_keeps_full_diagnostic_log(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'tests').mkdir()
            (root/'tests'/'test_bad.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_bad(self): self.fail("distinctive-error-017")\n')
            result = run_suite(root, timeout_per_module=10)
            module = result['modules'][0]
            self.assertEqual(module['status'], 'failed')
            self.assertIn('distinctive-error-017', Path(module['log_path']).read_text())
            self.assertFalse(result['passed'])

    def test_timeout_keeps_partial_output_for_diagnosis(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'tests').mkdir()
            (root/'tests'/'test_hang.py').write_text('import unittest,time\nclass T(unittest.TestCase):\n def test_hang(self):\n  print("before-hang-017", flush=True)\n  time.sleep(30)\n')
            result = run_suite(root, timeout_per_module=1)
            module = result['modules'][0]
            self.assertEqual(module['status'], 'timeout')
            self.assertIn('before-hang-017', Path(module['log_path']).read_text())
            self.assertFalse(result['passed'])

class RegressionResumeTests(unittest.TestCase):
    def test_resume_skips_only_passed_modules(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'tests').mkdir()
            marker=root/'calls'
            (root/'tests'/'test_a.py').write_text('import unittest\nfrom pathlib import Path\nclass T(unittest.TestCase):\n def test_ok(self):\n  p=Path('+repr(str(marker))+');p.write_text(p.read_text()+"x" if p.exists() else "x")\n')
            (root/'tests'/'test_b.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n')
            checkpoint=root/'progress.json'
            first=run_suite(root,progress_path=checkpoint,selected_modules={'test_a.py'})
            self.assertTrue(first['passed'])
            second=run_suite(root,progress_path=checkpoint,resume=True)
            self.assertTrue(second['passed'])
            self.assertEqual(marker.read_text(),'x')
            self.assertEqual(second['total_tests'],2)
            self.assertTrue(second['modules'][0]['resumed'])

    def test_resume_refuses_changed_source(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'tests').mkdir()
            source=root/'tests'/'test_a.py'
            source.write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n')
            checkpoint=root/'progress.json'
            self.assertTrue(run_suite(root,progress_path=checkpoint)['passed'])
            source.write_text(source.read_text()+'\n# changed\n')
            with self.assertRaisesRegex(ValueError,'Source changed'):
                run_suite(root,progress_path=checkpoint,resume=True)

    def test_resume_requires_checkpoint(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'tests').mkdir()
            (root/'tests'/'test_a.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): pass\n')
            with self.assertRaisesRegex(ValueError,'requires progress_path'):
                run_suite(root,resume=True)


class RegressionMissingSummaryTests(unittest.TestCase):
    def test_successful_exit_without_unittest_summary_is_rejected(self):
        import sys
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'tests').mkdir()
            (root/'tests'/'test_fake.py').write_text('import os\nos._exit(0)\n')
            result=run_suite(root,timeout_per_module=10)
            self.assertFalse(result['passed'])
            self.assertEqual(result['modules'][0]['status'],'no_tests')
            self.assertEqual(result['total_tests'],0)
    def test_real_unittest_summary_is_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'tests').mkdir()
            (root/'tests'/'test_real.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')
            result=run_suite(root,timeout_per_module=10)
            self.assertTrue(result['passed'])
            self.assertEqual(result['total_tests'],1)
