import json, os, sys, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock
from adm import engine, ollama_direct
from adm.engine import make_broken_demo, run_checked, SafetyError
from adm.ollama_direct import request_patch, direct_repair, NUM_CTX
from adm.recovery import inventory


class _Echo(BaseHTTPRequestHandler):
    seen = []
    def do_POST(self):
        _Echo.seen.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
        data = json.dumps({'response': json.dumps({'files': []})}).encode()
        self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
    def log_message(self, *a): pass


class ContextTests(unittest.TestCase):
    def test_request_pins_context_window_and_zero_temperature(self):
        srv = HTTPServer(('127.0.0.1', 0), _Echo)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            try: request_patch('ollama/qwen2.5-coder:3b', 'hi', endpoint=f'http://127.0.0.1:{srv.server_port}')
            except SafetyError: pass          # empty 'files' envelope is rejected later; payload is what matters
        finally:
            srv.shutdown()
        self.assertEqual(_Echo.seen[-1]['options'], {'num_ctx': NUM_CTX, 'temperature': 0})

    def test_oversized_source_file_fails_closed_instead_of_truncating(self):
        with tempfile.TemporaryDirectory() as t:
            proj, ev = Path(t) / 'p', Path(t) / 'e'
            make_broken_demo(proj)
            (proj / 'calculator.py').write_text('def add(a, b):\n    return a - b\n' + '# pad\n' * 6000, newline='')
            called = []
            report = direct_repair(proj, ev, max_repairs=1, generator=lambda *a, **k: called.append(1))
            self.assertEqual(called, [])
            self.assertIn('too large', report['attempts'][0]['error'])

    def test_inference_timeout_is_separate_from_test_timeout(self):
        with tempfile.TemporaryDirectory() as t:
            proj, ev = Path(t) / 'p', Path(t) / 'e'
            make_broken_demo(proj)
            got = {}
            def gen(model, prompt, timeout):
                got['timeout'] = timeout
                raise SafetyError('stop')
            direct_repair(proj, ev, max_repairs=1, timeout=30, generator=gen)
            self.assertEqual(got['timeout'], ollama_direct.DEFAULT_INFERENCE_TIMEOUT)
            self.assertGreater(got['timeout'], 30)


class OutputCapTests(unittest.TestCase):
    def test_runaway_output_is_stopped_and_bounded(self):
        with tempfile.TemporaryDirectory() as t, mock.patch.object(engine, 'MAX_CAPTURE_BYTES', 1_000_000):
            code = 'import sys\nwhile True: sys.stdout.write("x"*10000)'
            r = run_checked([sys.executable, '-c', code], t, t, timeout=30, output_limit=2000)
            self.assertEqual(r['exit_code'], 124)
            self.assertIn('exceeded', r['output'])
            self.assertLessEqual(len(r['output']), 2000)

    def test_normal_output_and_exit_code_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            r = run_checked([sys.executable, '-c', 'import sys;print("out");print("err",file=sys.stderr);sys.exit(3)'], t, t)
            self.assertEqual(r['exit_code'], 3)
            self.assertIn('out', r['output']); self.assertIn('err', r['output'])


class SmallFixTests(unittest.TestCase):
    def test_excluded_dirs_may_contain_symlinks(self):
        if os.name == 'nt': self.skipTest('symlink creation needs privileges on Windows')
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); (root / '.venv').mkdir(); (root / 'a.py').write_text('x')
            os.symlink(root / 'a.py', root / '.venv' / 'link')
            self.assertEqual(list(inventory(root)), ['a.py'])

    def test_schtasks_command_too_long_is_rejected(self):
        from adm.windows_startup import windows_task_command
        with tempfile.TemporaryDirectory() as t:
            deep = Path(t, *['d' * 40] * 8); deep.mkdir(parents=True)
            with self.assertRaises(ValueError):
                windows_task_command(str(deep))

    def test_find_executable_falls_back_to_default_dirs_on_windows_only(self):
        from adm import setup
        with mock.patch.object(setup.shutil, 'which', return_value=None), mock.patch.object(setup.os, 'name', 'posix'):
            self.assertIsNone(setup.find_executable('ollama'))


if __name__ == '__main__':
    unittest.main()
