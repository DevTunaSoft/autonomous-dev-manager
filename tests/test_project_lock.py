import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from adm.engine import SafetyError
from adm.project_lock import exclusive_project

class ProjectLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_metadata_and_persistent_lock_file(self):
        with exclusive_project(self.root) as record:
            self.assertEqual(json.loads((self.root/'.adm-repair.lock').read_text())['token'],record['token'])
        self.assertTrue((self.root/'.adm-repair.lock').exists())
        with exclusive_project(self.root): pass

    def test_same_process_second_owner_refused(self):
        with exclusive_project(self.root):
            with self.assertRaises(SafetyError):
                with exclusive_project(self.root): pass

    def test_abandoned_metadata_does_not_block_recovery(self):
        (self.root/'.adm-repair.lock').write_text('stale')
        with exclusive_project(self.root): pass

    def test_exception_releases_kernel_lock(self):
        with self.assertRaisesRegex(RuntimeError,'failure'):
            with exclusive_project(self.root): raise RuntimeError('failure')
        with exclusive_project(self.root): pass

    def test_cross_process_exclusion_and_recovery(self):
        code = ('from adm.project_lock import exclusive_project; from adm.engine import SafetyError; '
                'import sys\ntry:\n with exclusive_project(sys.argv[1]): pass\nexcept SafetyError: sys.exit(9)')
        with exclusive_project(self.root):
            result = subprocess.run([sys.executable,'-c',code,str(self.root)],cwd=Path(__file__).resolve().parents[1],capture_output=True)
            self.assertEqual(result.returncode,9,result.stderr.decode())
        result = subprocess.run([sys.executable,'-c',code,str(self.root)],cwd=Path(__file__).resolve().parents[1],capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr.decode())

    def test_crashed_process_releases_ownership(self):
        code = ('from adm.project_lock import exclusive_project; import os,sys\n'
                'with exclusive_project(sys.argv[1]): os._exit(23)')
        result = subprocess.run([sys.executable,'-c',code,str(self.root)],cwd=Path(__file__).resolve().parents[1],capture_output=True)
        self.assertEqual(result.returncode,23,result.stderr.decode())
        with exclusive_project(self.root): pass

    def test_symlink_refused(self):
        target = self.root/'target'; target.write_text('untouched')
        try: (self.root/'.adm-repair.lock').symlink_to(target)
        except (OSError,NotImplementedError): self.skipTest('symlink unavailable')
        with self.assertRaises(SafetyError):
            with exclusive_project(self.root): pass
        self.assertEqual(target.read_text(),'untouched')

if __name__=='__main__': unittest.main()
