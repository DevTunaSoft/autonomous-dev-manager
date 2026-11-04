import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from adm.release import create_source_release, verify_source_release, windows_build_plan, build_windows_executable

class ReleaseTests(unittest.TestCase):
    def make_project(self, root):
        (root / 'adm').mkdir(); (root / 'tests').mkdir()
        (root / 'adm' / '__init__.py').write_text('')
        (root / 'adm' / 'daemon.py').write_text('print(1)')
        (root / 'tests' / 'test_demo.py').write_text('assert True')

    def test_complete_package_and_manifest(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)/'project'; root.mkdir(); self.make_project(root)
            dest = Path(t)/'complete.zip'
            result = create_source_release(root, dest)
            self.assertEqual(result['file_count'], 3)
            self.assertEqual(verify_source_release(dest), 3)
            self.assertEqual(result['sha256'], hashlib.sha256(dest.read_bytes()).hexdigest())

    def test_deterministic_package(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'p'; root.mkdir(); self.make_project(root)
            a=Path(t)/'a.zip'; b=Path(t)/'b.zip'
            create_source_release(root,a); create_source_release(root,b)
            self.assertEqual(a.read_bytes(),b.read_bytes())

    def test_reject_destination_inside_project(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); self.make_project(root)
            with self.assertRaises(ValueError): create_source_release(root,root/'source.zip')

    def test_exclude_sensitive_state_and_cache(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'p'; root.mkdir(); self.make_project(root)
            (root/'.adm-state').mkdir(); (root/'.adm-state'/'secret').write_text('SECRET')
            (root/'adm'/'__pycache__').mkdir(); (root/'adm'/'__pycache__'/'a.pyc').write_bytes(b'cache')
            dest=Path(t)/'a.zip'; create_source_release(root,dest)
            with zipfile.ZipFile(dest) as z:
                self.assertFalse(any('secret' in x or 'pycache' in x for x in z.namelist()))

    def test_tamper_detected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'p'; root.mkdir(); self.make_project(root)
            dest=Path(t)/'a.zip'; create_source_release(root,dest)
            with zipfile.ZipFile(dest,'a') as z:
                z.writestr('ADM/extra.py','bad')
            with self.assertRaises(ValueError): verify_source_release(dest)

    def test_windows_plan_and_approval(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); self.make_project(root)
            self.assertIn('PyInstaller',windows_build_plan(root))
            with self.assertRaises(PermissionError): build_windows_executable(root)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'p'; root.mkdir(); self.make_project(root)
            link=root/'adm'/'external'
            try: link.symlink_to(Path(t))
            except (OSError,NotImplementedError): self.skipTest('symlink unavailable')
            with self.assertRaises(ValueError): create_source_release(root,Path(t)/'out.zip')

class FrozenStartupTests(unittest.TestCase):
    def test_frozen_launcher_uses_exe_directly(self):
        from unittest.mock import patch
        from adm.windows_startup import startup_command
        import sys
        with patch.object(sys, 'frozen', True, create=True):
            argv = startup_command('.')
        self.assertNotIn('-m', argv)
        self.assertEqual(argv[1:3], ['--adm-supervisor', '--state'])
