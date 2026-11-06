import subprocess
import unittest
from unittest.mock import patch
from adm.setup import build_plan, choose_model, execute_step

GIB = 1024**3


def hw(available, disk=80):
    return {'ram_available_bytes': available*GIB, 'disk_free_bytes': disk*GIB}


class SetupTests(unittest.TestCase):
    def test_constrained_machine(self):
        self.assertEqual(choose_model(hw(5)), 'qwen2.5-coder:1.5b')

    def test_balanced_machine(self):
        self.assertEqual(choose_model(hw(12)), 'qwen2.5-coder:3b')

    def test_performance_machine(self):
        self.assertEqual(choose_model(hw(24)), 'qwen2.5-coder:7b')

    def test_slow_disk_low_space_falls_back(self):
        self.assertEqual(choose_model(hw(24, 5)), 'qwen2.5-coder:1.5b')

    def test_windows_plan_no_tools(self):
        p = build_plan(system='Windows', binaries={}, hardware=hw(6))
        self.assertEqual([x['key'] for x in p['steps']], [])
        self.assertTrue(any('winget' in x for x in p['blockers']))
        self.assertFalse(p['automatic_setup_complete'])

    def test_windows_plan_with_winget(self):
        p = build_plan(system='Windows', binaries={'winget': 'winget.exe'}, hardware=hw(12))
        self.assertEqual([x['key'] for x in p['steps']], ['install_ollama', 'pull_model'])

    def test_linux_never_provisions(self):
        p = build_plan(system='Linux', binaries={}, hardware=hw(12))
        self.assertEqual(p['steps'], [])

    def test_unknown_model_rejected(self):
        with self.assertRaises(ValueError):
            build_plan(system='Windows', binaries={}, hardware=hw(12), model='untrusted')

    def test_approval_required(self):
        with self.assertRaises(PermissionError):
            execute_step({'key':'pull_model', 'argv':['ollama','pull','qwen2.5-coder:3b']}, system='Windows')

    def test_unknown_commands_rejected(self):
        with self.assertRaises(ValueError):
            execute_step({'key':'install_ollama', 'argv':['winget','install','malware']}, approved=True, system='Windows')

    def test_unapproved_model_rejected(self):
        with self.assertRaises(ValueError):
            execute_step({'key':'pull_model', 'argv':['ollama','pull','evil/model']}, approved=True, system='Windows')

    def test_execution_mock(self):
        completed = subprocess.CompletedProcess(['ollama'], 0, 'ok', '')
        with patch('adm.setup.shutil.which', return_value='C:/ollama.exe'):
            result = execute_step({'key':'pull_model','argv':['ollama','pull','qwen2.5-coder:3b']},
                                  approved=True, system='Windows', runner=lambda *a, **k: completed)
        self.assertEqual(result['status'], 'completed')

    def test_missing_executable_blocks(self):
        with patch('adm.setup.shutil.which', return_value=None):
            result = execute_step({'key':'pull_model','argv':['ollama','pull','qwen2.5-coder:3b']},
                                  approved=True, system='Windows')
        self.assertEqual(result['status'], 'blocked')

    def test_timeout_reported(self):
        def fail(*a, **kw):
            raise subprocess.TimeoutExpired('ollama', 5)
        with patch('adm.setup.shutil.which', return_value='ollama'):
            result = execute_step({'key':'pull_model','argv':['ollama','pull','qwen2.5-coder:3b']},
                                  approved=True, system='Windows', runner=fail)
        self.assertEqual(result['status'], 'failed')


class MalformedInputTests(unittest.TestCase):
    def test_execute_step_rejects_non_dict_step(self):
        for step in (None, [], 'x', 42):
            with self.assertRaises(ValueError):
                execute_step(step, approved=True, system='Windows')

    def test_build_plan_rejects_non_mapping_binaries_or_hardware(self):
        hw = {'ram_available_bytes': 16 * GIB, 'disk_free_bytes': 100 * GIB}
        with self.assertRaises(ValueError):
            build_plan(system='Windows', binaries='notadict', hardware=hw)
        with self.assertRaises(ValueError):
            build_plan(system='Windows', binaries={}, hardware='notadict')


if __name__ == '__main__':
    unittest.main()
