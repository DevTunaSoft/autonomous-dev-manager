import tempfile, unittest
from pathlib import Path
from adm import runtime_install
from adm.engine import SafetyError


class RuntimeInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def _fake_embed(self):
        src = self.base / 'pyembed'
        src.mkdir()
        (src / 'python.exe').write_bytes(b'MZ')          # stand-in for the interpreter
        (src / 'python312._pth').write_text('python312.zip\n#import site\n', encoding='utf-8')
        return src

    def test_shared_dir_honours_programdata_override(self):
        d = runtime_install.shared_python_dir(programdata=str(self.base / 'PD'))
        self.assertEqual(d, self.base / 'PD' / 'ADM' / 'python')

    def test_fixup_pth_enables_cwd_and_site(self):
        src = self._fake_embed()
        runtime_install.fixup_pth(src)
        text = (src / 'python312._pth').read_text()
        self.assertIn('\n.', '\n' + text)         # a bare '.' line was added
        self.assertIn('import site', text)
        self.assertNotIn('#import site', text)

    def test_install_copies_once_and_is_idempotent(self):
        src = self._fake_embed()
        pd = self.base / 'PD'
        exe = runtime_install.ensure_shared_python(src, programdata=str(pd))
        self.assertTrue(exe.is_file())
        self.assertEqual(exe, pd / 'ADM' / 'python' / 'python.exe')
        # the copied runtime had its _pth fixed
        self.assertIn('import site', (pd / 'ADM' / 'python' / 'python312._pth').read_text())
        # calling again returns the same path without re-copying (mark the file and check it survives)
        exe.write_bytes(b'MARKED')
        again = runtime_install.ensure_shared_python(src, programdata=str(pd))
        self.assertEqual(again.read_bytes(), b'MARKED')

    def test_install_refuses_a_source_without_python(self):
        (self.base / 'empty').mkdir()
        with self.assertRaises(SafetyError):
            runtime_install.ensure_shared_python(self.base / 'empty', programdata=str(self.base / 'PD'))

    def test_ensure_runtime_is_a_noop_without_a_bundle(self):
        self.assertIsNone(runtime_install.ensure_runtime())   # not frozen in tests


    def test_fixup_pth_tolerates_non_utf8_pth(self):
        # A corrupt/non-UTF8 ._pth must not crash the runtime install; the file
        # is still fixed to contain '.' and 'import site'.
        d = Path(self.tmp.name) / 'binpth'
        d.mkdir()
        (d / 'python312._pth').write_bytes(b'python312.zip\r\n\xff\xfe\x00bad\n#import site\n')
        res = runtime_install.fixup_pth(d)                 # must not raise
        self.assertIsNotNone(res)
        txt = res.read_text(encoding='utf-8', errors='replace')
        self.assertIn('.', txt.splitlines())
        self.assertIn('import site', txt)


if __name__ == '__main__':
    unittest.main()
