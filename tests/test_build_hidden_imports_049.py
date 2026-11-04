import unittest
from pathlib import Path
from adm.selftest import SMOKE_MODULES

ROOT = Path(__file__).resolve().parent.parent


class BuildHiddenImportTests(unittest.TestCase):
    def test_every_smoke_module_is_a_pyinstaller_hidden_import(self):
        # Regression: ADM-049 Windows CI showed adm.model_selection missing from the EXE.
        build = (ROOT / 'BUILD-WINDOWS-DESKTOP.cmd').read_text(encoding='utf-8')
        for name in SMOKE_MODULES:
            self.assertIn('--hidden-import ' + name + ' ', build + ' ', name)


if __name__ == '__main__':
    unittest.main()
