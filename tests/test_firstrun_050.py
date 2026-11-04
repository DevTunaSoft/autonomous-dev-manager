import tempfile, unittest
from pathlib import Path
from adm import firstrun
from adm.pyruntime import PythonNotFound


def _assess(**kw):
    base = dict(ram_gib=16, find_exe=lambda n: None, inspect=lambda timeout=3: (_ for _ in ()).throw(OSError('down')),
                python_finder=lambda: '/usr/bin/python3', env={}, home=Path(tempfile.gettempdir()) / 'u', winget=True)
    base.update(kw)
    return firstrun.assess(**base)


class AssessTests(unittest.TestCase):
    def test_fresh_pc_needs_ollama_and_model(self):
        a = _assess()
        self.assertEqual(a['needs'], ['ollama', 'model'])
        self.assertFalse(a['ready'])
        self.assertEqual(a['recommended_model'], 'qwen2.5-coder:3b')

    def test_model_choice_follows_physical_ram(self):
        self.assertEqual(firstrun.recommend_model(4), 'qwen2.5-coder:1.5b')
        self.assertEqual(firstrun.recommend_model(16), 'qwen2.5-coder:3b')
        self.assertEqual(firstrun.recommend_model(32), 'qwen2.5-coder:7b')

    def test_installed_but_stopped_ollama(self):
        a = _assess(find_exe=lambda n: 'C:/ollama.exe')
        self.assertEqual(a['needs'], ['start_ollama', 'model'])

    def test_ready_when_usable_coder_model_installed(self):
        a = _assess(find_exe=lambda n: 'C:/ollama.exe',
                    inspect=lambda timeout=3: {'installed_models': ['qwen2.5-coder:3b']})
        self.assertTrue(a['ready'])
        self.assertEqual(a['usable_model'], 'ollama/qwen2.5-coder:3b')

    def test_unfit_or_unrelated_models_do_not_count(self):
        a = _assess(find_exe=lambda n: 'C:/ollama.exe',
                    inspect=lambda timeout=3: {'installed_models': ['llama3:8b', 'qwen2.5-coder:7b']}, ram_gib=16)
        self.assertIn('model', a['needs'])           # 7b is too big for 16 GB by ADM's conservative rule

    def test_missing_python_is_reported_but_not_installable(self):
        def nope(): raise PythonNotFound('no python')
        a = _assess(python_finder=nope)
        self.assertIn('python', a['needs'])
        self.assertFalse(a['python']['found'])

    def test_models_dir_default_and_override(self):
        self.assertEqual(firstrun.models_dir({}, Path('/home/u')), Path('/home/u/.ollama/models'))
        self.assertEqual(firstrun.models_dir({'OLLAMA_MODELS': 'D:/m'}, Path('/home/u')), Path('D:/m'))


class PromptTests(unittest.TestCase):
    def test_prompt_says_what_size_and_where(self):
        _, text = firstrun.prompt_text(_assess(home=Path('/home/u')))
        self.assertIn('qwen2.5-coder:3b', text)
        self.assertIn('2.0 GB', text)
        self.assertIn('.ollama', text)
        self.assertIn('Download and set up now?', text)

    def test_no_installer_offer_without_winget(self):
        _, text = firstrun.prompt_text(_assess(winget=False))
        self.assertIn('ollama.com/download', text)

    def test_python_only_gap_has_no_download_question(self):
        def nope(): raise PythonNotFound('x')
        a = _assess(find_exe=lambda n: 'C:/o.exe', inspect=lambda timeout=3: {'installed_models': ['qwen2.5-coder:3b']}, python_finder=nope)
        _, text = firstrun.prompt_text(a)
        self.assertNotIn('Download and set up now?', text)
        self.assertIn('python.org', text)


class RunSetupTests(unittest.TestCase):
    def test_refuses_without_approval(self):
        with self.assertRaises(PermissionError):
            firstrun.run_setup(_assess(), approved=False, on_status=print)

    def test_full_flow_installs_starts_and_pulls_in_order(self):
        calls, said = [], []
        exes = iter([None, 'C:/ollama.exe'])
        out = firstrun.run_setup(
            _assess(), approved=True, on_status=said.append,
            executor=lambda step, approved, system: calls.append(('install', step['key'])) or {'status': 'completed'},
            starter=lambda exe: calls.append(('start', exe)) or True,
            puller=lambda exe, model, cb: (cb('pulling 10%'), calls.append(('pull', model)), {'status': 'completed'})[2],
            finder=lambda n: 'C:/ollama.exe')
        self.assertEqual(out['status'], 'completed')
        self.assertEqual(calls, [('install', 'install_ollama'), ('start', 'C:/ollama.exe'), ('pull', 'qwen2.5-coder:3b')])
        self.assertTrue(any('pulling 10%' in s for s in said))

    def test_failed_install_stops_before_download(self):
        calls = []
        out = firstrun.run_setup(_assess(), approved=True, on_status=print,
                                 executor=lambda *a, **k: {'status': 'failed', 'reason': 'boom'},
                                 puller=lambda *a: calls.append('pull'), starter=lambda e: True, finder=lambda n: None)
        self.assertEqual(out['status'], 'failed')
        self.assertEqual(calls, [])

    def test_no_winget_gives_manual_instructions(self):
        out = firstrun.run_setup(_assess(winget=False), approved=True, on_status=print)
        self.assertEqual(out['status'], 'manual')
        self.assertIn('ollama.com/download', out['message'])

    def test_only_allowlisted_model_can_be_pulled(self):
        with self.assertRaises(ValueError):
            firstrun.pull_with_progress('ollama', 'evil/model', print)

    def test_progress_lines_are_streamed(self):
        import sys, tempfile, os
        with tempfile.TemporaryDirectory() as t:
            fake = os.path.join(t, 'fake.py')
            Path(fake).write_text('import sys\nsys.stdout.write("pulling manifest\\npulling aaa 10%\\rpulling aaa 90%\\rsuccess\\n")')
            wrapper = os.path.join(t, 'ollama.cmd' if os.name == 'nt' else 'ollama')
            if os.name == 'nt':
                Path(wrapper).write_text(f'@"{sys.executable}" "{fake}" %*\r\n', newline='')
            else:
                Path(wrapper).write_text(f'#!/bin/sh\nexec "{sys.executable}" "{fake}" "$@"\n'); os.chmod(wrapper, 0o755)
            lines = []
            res = firstrun.pull_with_progress(wrapper, 'qwen2.5-coder:3b', lines.append)
            self.assertEqual(res['status'], 'completed')
            self.assertEqual(lines, ['pulling manifest', 'pulling aaa 10%', 'pulling aaa 90%', 'success'])


if __name__ == '__main__':
    unittest.main()
