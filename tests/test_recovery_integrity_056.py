"""ADM-056: evidence corruption never triggers destructive cleanup."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adm import build, intake
from adm.engine import SafetyError
from adm.repair_recovery import prepare_journal


class EvidenceRecoveryIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'project'
        self.root.mkdir()
        self.code = self.root / 'app.py'
        self.original = b'def value():\n    return 1\n'
        self.code.write_bytes(self.original)
        self.ev = self.base / 'evidence'

    def test_clean_uncreated_evidence_is_noop(self):
        build._recover_interrupted(self.root, self.ev)
        self.assertFalse(self.ev.exists())
        self.assertEqual(self.code.read_bytes(), self.original)

    def test_corrupted_journal_blocks_and_preserves_all_bytes(self):
        self.ev.mkdir()
        journal = self.ev / 'repair-journal.json'
        bad = b'{not valid json'
        journal.write_bytes(bad)
        with self.assertRaises(SafetyError):
            build._recover_interrupted(self.root, self.ev)
        self.assertEqual(journal.read_bytes(), bad)
        self.assertEqual(self.code.read_bytes(), self.original)

    def test_unexpected_source_change_blocks_and_preserves_evidence(self):
        prepare_journal(self.root, self.ev, {'files': [
            {'path': 'app.py', 'content': 'def value():\n    return 2\n'}]})
        self.code.write_text('def value():\n    return 900\n', encoding='utf-8')
        prior = (self.ev / 'repair-journal.json').read_bytes()
        with self.assertRaisesRegex(SafetyError, 'unexpected source change'):
            build._recover_interrupted(self.root, self.ev)
        self.assertEqual((self.ev / 'repair-journal.json').read_bytes(), prior)
        self.assertIn('900', self.code.read_text(encoding='utf-8'))

    def test_valid_crash_journal_recovers_and_clears_evidence(self):
        replacement = 'def value():\n    return 2\n'
        prepare_journal(self.root, self.ev, {'files': [{'path': 'app.py', 'content': replacement}]})
        self.code.write_text(replacement, encoding='utf-8')
        build._recover_interrupted(self.root, self.ev)
        self.assertEqual(self.code.read_bytes(), self.original)
        self.assertFalse(self.ev.exists())

    def test_root_and_ancestor_evidence_paths_blocked_before_deletion(self):
        for path in (self.root, self.root / 'internal', self.base):
            with self.subTest(path=str(path)), self.assertRaisesRegex(SafetyError, 'overlaps'):
                build._recover_interrupted(self.root, path)
            self.assertEqual(self.code.read_bytes(), self.original)
        self.assertTrue(self.root.exists())
        self.assertTrue(self.base.exists())

    def test_evidence_not_directory_is_refused(self):
        self.ev.write_text('important unrelated data', encoding='utf-8')
        with self.assertRaisesRegex(SafetyError, 'directory'):
            build._recover_interrupted(self.root, self.ev)
        self.assertEqual(self.ev.read_text(), 'important unrelated data')

    def test_unrecognized_evidence_contents_not_deleted(self):
        self.ev.mkdir()
        marker = self.ev / 'ollama-direct-report.json'
        marker.write_text('{}', encoding='utf-8')
        important = self.ev / 'important.txt'
        important.write_text('must preserve', encoding='utf-8')
        with self.assertRaisesRegex(SafetyError, 'Unknown or unsafe'):
            build._recover_interrupted(self.root, self.ev)
        self.assertEqual(important.read_text(), 'must preserve')
        self.assertTrue(marker.exists())

    def test_orphan_output_without_adm_marker_is_preserved(self):
        self.ev.mkdir()
        orphan = self.ev / 'baseline-output.log'
        orphan.write_bytes(b'uncertain owner')
        with self.assertRaisesRegex(SafetyError, 'lacks an ADM journal/report'):
            build._recover_interrupted(self.root, self.ev)
        self.assertEqual(orphan.read_bytes(), b'uncertain owner')

    def test_symlink_evidence_root_refused(self):
        try:
            self.ev.symlink_to(self.root, target_is_directory=True)
        except (NotImplementedError, OSError):
            self.skipTest('Creating directory symlinks requires permission')
        with self.assertRaisesRegex(SafetyError, 'symlink'):
            build._recover_interrupted(self.root, self.ev)
        self.assertTrue(self.root.exists())

    def test_symlink_inside_evidence_refused(self):
        self.ev.mkdir()
        try:
            (self.ev / 'ollama-direct-report.json').symlink_to(self.code)
        except (NotImplementedError, OSError):
            self.skipTest('Creating symlinks requires permission')
        with self.assertRaisesRegex(SafetyError, 'Unknown or unsafe'):
            build._recover_interrupted(self.root, self.ev)
        self.assertEqual(self.code.read_bytes(), self.original)

    def test_malformed_report_is_preserved_for_diagnosis(self):
        self.ev.mkdir()
        report = self.ev / 'ollama-direct-report.json'
        for bad in (b'{bad report', b'[]', b'{}', b'\xff\xfe'):
            with self.subTest(bad=bad):
                report.write_bytes(bad)
                with self.assertRaises(SafetyError):
                    build._recover_interrupted(self.root, self.ev)
                self.assertEqual(report.read_bytes(), bad)
                self.assertEqual(self.code.read_bytes(), self.original)

    def test_cleanup_errors_no_longer_silenced(self):
        self.ev.mkdir()
        (self.ev / 'ollama-direct-report.json').write_text('{"status":"repair_failed"}', encoding='utf-8')
        with patch('shutil.rmtree', side_effect=PermissionError('file is locked')):
            with self.assertRaisesRegex(SafetyError, 'Could not clear'):
                build._recover_interrupted(self.root, self.ev)
        self.assertTrue(self.ev.is_dir())
        self.assertEqual(self.code.read_bytes(), self.original)

    def test_full_build_fails_closed_on_bad_journal(self):
        home = self.base / 'home'
        home.mkdir()
        state = self.base / 'state'
        plan_data = {'title': 'Simple adder', 'summary': 'Adds two numbers',
                     'features': ['Add numbers'], 'tests': ['When adding 1 and 2 result is 3'],
                     'needs_internet': False, 'questions': []}
        plan = intake.create_plan(state, 'Build adder', mode='new', folder='',
                                  generator=lambda *a, **kw: plan_data,
                                  model='ollama/local', home=home)
        approved = intake.approve(plan['path'])
        folder = Path(approved['folder'])
        self.assertNotEqual(folder, self.root)
        saved = b'important source\n'
        (folder / 'app.py').write_bytes(saved)
        ev = self.base / 'build-evidence'
        ev.mkdir()
        journal = ev / 'repair-journal.json'
        journal.write_bytes(b'{broken')
        with self.assertRaises(SafetyError):
            build.build_from_plan(
                approved['path'], ev,
                test_generator=lambda *a, **kw: self.fail('No inference should begin'),
                code_generator=lambda *a, **kw: self.fail('No code generated'),
                model='ollama/local', require_sandbox=False)
        self.assertEqual((folder / 'app.py').read_bytes(), saved)
        self.assertEqual(journal.read_bytes(), b'{broken')

    def test_evidence_path_matching_project_cannot_delete_it(self):
        self.ev.mkdir()
        (self.ev / 'ollama-direct-report.json').write_text('{}', encoding='utf-8')
        # Using the project itself as evidence would otherwise rmtree the code.
        with self.assertRaises(SafetyError):
            build._recover_interrupted(self.root, self.root)
        self.assertEqual(self.code.read_bytes(), self.original)


if __name__ == '__main__':
    unittest.main()
