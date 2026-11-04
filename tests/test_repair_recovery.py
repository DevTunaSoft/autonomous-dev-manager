import json
import tempfile
import unittest
from pathlib import Path
from adm.repair_recovery import prepare_journal, recover_journal, finish_journal
from adm.engine import SafetyError

class RepairRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()
        self.evidence = Path(self.tmp.name) / 'evidence'
        (self.root / 'app.py').write_text('old = 1\n', newline='')
        self.patch = {'files': [{'path': 'app.py', 'content': 'new = 2\n'}]}

    def test_interrupted_replacement_restores_original(self):
        prepare_journal(self.root, self.evidence, self.patch)
        (self.root / 'app.py').write_text('new = 2\n', newline='')
        self.assertTrue(recover_journal(self.root, self.evidence))
        self.assertEqual((self.root / 'app.py').read_text(), 'old = 1\n')
        self.assertFalse(recover_journal(self.root, self.evidence))

    def test_unexpected_edit_blocks_recovery(self):
        prepare_journal(self.root, self.evidence, self.patch)
        (self.root / 'app.py').write_text('someone_else = 3\n', newline='')
        with self.assertRaises(SafetyError):
            recover_journal(self.root, self.evidence)
        self.assertTrue((self.evidence / 'repair-journal.json').exists())

    def test_project_mismatch_blocks_recovery(self):
        prepare_journal(self.root, self.evidence, self.patch)
        other = Path(self.tmp.name) / 'other'
        other.mkdir()
        (other / 'app.py').write_text('old = 1\n', newline='')
        with self.assertRaises(SafetyError):
            recover_journal(other, self.evidence)

    def test_symlink_swap_blocks_recovery(self):
        prepare_journal(self.root, self.evidence, self.patch)
        target = self.root / 'other.py'
        target.write_text('untouched', newline='')
        (self.root / 'app.py').unlink()
        try:
            (self.root / 'app.py').symlink_to(target)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaises(SafetyError):
            recover_journal(self.root, self.evidence)
        self.assertEqual(target.read_text(), 'untouched')

    def test_finish_commits_successful_repair(self):
        prepare_journal(self.root, self.evidence, self.patch)
        (self.root / 'app.py').write_text('new = 2\n', newline='')
        finish_journal(self.evidence)
        self.assertFalse(recover_journal(self.root, self.evidence))
        self.assertEqual((self.root / 'app.py').read_text(), 'new = 2\n')

if __name__ == '__main__':
    unittest.main()
