"""Regression tests for bugs found by tools/fuzz_adversarial.py, plus the tolerant-parser retry."""
import json
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from adm import backends, intake, sandbox
from adm.ollama_direct import apply_patch, request_json
from adm.engine import SafetyError


class ExtractJsonTests(unittest.TestCase):
    def test_tolerates_wrapping(self):
        self.assertEqual(backends.extract_json('{"a": 1}'), {'a': 1})
        self.assertEqual(backends.extract_json('```json\n{"a": 1}\n```'), {'a': 1})
        self.assertEqual(backends.extract_json('Sure! Here it is: {"a": 1} hope that helps'), {'a': 1})
        self.assertEqual(backends.extract_json('{"a": 1,}'), {'a': 1})          # trailing comma
        self.assertEqual(backends.extract_json('[{"x": "}"}]'), [{'x': '}'}])    # brace inside string

    def test_rejects_garbage_without_crashing(self):
        for bad in ['', '   ', 'not json', '{', '}{', None, 123, b'{}', '{"a":', 'null and more words']:
            with self.assertRaises(SafetyError):
                backends.extract_json(bad)

    def test_deeply_nested_input_cannot_crash_the_parser(self):
        # On some Python versions json raises RecursionError; it must become a clean reject, not a crash.
        original = backends.json.loads

        def boom(*a, **k):
            raise RecursionError('maximum recursion depth exceeded')
        backends.json.loads = boom
        try:
            with self.assertRaises(SafetyError):
                backends.extract_json('[1, 2, 3]')
        finally:
            backends.json.loads = original


class ApplyPatchGuardTests(unittest.TestCase):
    def test_non_envelope_inputs_are_rejected_cleanly(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for bad in [None, {}, {'files': 'x'}, {'files': None}, 42, 'nope']:
                with self.assertRaises(SafetyError):
                    apply_patch(root, bad)


class PathHardeningTests(unittest.TestCase):
    def test_absurdly_long_path_is_a_clean_reject(self):
        with self.assertRaises(SafetyError):
            intake.check_existing_folder('a' * 5000)          # must not leak OSError

    def test_system_folders_rejected(self):
        for v in (r'C:\Windows', r'c:\windows\system32', r'C:\Program Files\x', 'C:\\'):
            with self.assertRaises(SafetyError):
                intake.check_existing_folder(v)


class CmdlineHardeningTests(unittest.TestCase):
    def test_metacharacters_and_trailing_backslash_rejected(self):
        for a in (['a&b'], ['a|b'], ['a>b'], ['a<b'], ['a^b'], ['ok', 'c:\\dir\\'], [''], ['x\x00'], ['%P%']):
            with self.assertRaises(SafetyError):
                sandbox.cmdline_for(a, r'C:\o\out.txt')

    def test_real_command_accepted(self):
        line = sandbox.cmdline_for(['py.exe', '-m', 'unittest', 'discover', '-s', '.', '-p', 'test_*.py'], r'C:\o.txt')
        self.assertIn('unittest', line)


class PlanFileHardeningTests(unittest.TestCase):
    def test_non_dict_plan_file_is_rejected(self):
        import tempfile
        from pathlib import Path
        from adm import intake
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'plan.json'
            for bad in ('[]', 'null', '"x"', '[1,2,3]', '42'):
                p.write_text(bad)
                with self.assertRaises(SafetyError):
                    intake.load_plan(str(p))
                with self.assertRaises(SafetyError):
                    intake.require_approved(str(p))


class ExtendedLengthPathTests(unittest.TestCase):
    def test_backslash_qmark_prefix_cannot_bypass_hardened_check(self):
        for v in (r'\\?\C:\Users\Public\x', r'\\?\C:\ProgramData', r'\\.\C:\Windows\Temp\x'):
            with self.assertRaises(SafetyError):
                sandbox.refuse_hardened_location(v)

    def test_backslash_qmark_prefix_cannot_bypass_system_folder_check(self):
        from adm import intake
        for v in (r'\\?\C:\Windows', r'\\?\C:\Windows\System32', r'\\?\C:\\'):
            with self.assertRaises(SafetyError):
                intake.check_existing_folder(v)


class RetryTests(unittest.TestCase):
    def _server(self, replies):
        box = {'n': 0}
        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                content = replies[min(box['n'], len(replies) - 1)]
                box['n'] += 1
                body = json.dumps({'response': content}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *a):
                pass
        srv = HTTPServer(('127.0.0.1', 0), H)
        Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        srv.calls = box
        return srv

    def test_request_json_recovers_from_messy_first_answer(self):
        srv = self._server(['here is your answer, friend:', '{"files": [{"path": "app.py", "content": "x=1\\n"}]}'])
        endpoint = 'http://127.0.0.1:%d' % srv.server_port
        result = request_json('ollama/test', 'please', endpoint=endpoint, timeout=10)
        self.assertEqual(result['files'][0]['path'], 'app.py')
        self.assertEqual(srv.calls['n'], 2)                   # it re-asked exactly once

    def test_request_json_gives_up_after_one_retry(self):
        srv = self._server(['nonsense only'])                 # always junk
        endpoint = 'http://127.0.0.1:%d' % srv.server_port
        with self.assertRaises(SafetyError):
            request_json('ollama/test', 'please', endpoint=endpoint, timeout=10)
        self.assertEqual(srv.calls['n'], 2)                   # original + one retry, then stop


if __name__ == '__main__':
    unittest.main()
