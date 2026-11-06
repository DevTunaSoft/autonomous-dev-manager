import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from adm.engine import SafetyError, make_broken_demo
from adm.ollama_direct import apply_patch, direct_repair, request_patch

class DirectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = make_broken_demo(self.base / 'project')
        self.evidence = self.base / 'evidence'

    def test_successful_repair_from_fake_generator(self):
        def fake(model, prompt, timeout):
            self.assertIn('calculator.py', prompt)
            return {'files': [{'path': 'calculator.py', 'content': 'def add(a,b):\n    return a+b\n'}]}
        result = direct_repair(self.root, self.evidence, generator=fake)
        self.assertEqual(result['status'], 'verified_direct_repair')
        self.assertFalse(result['live_model_verified'])
        self.assertEqual(len(result['attempts']), 1)

    def test_faulty_test_runner_never_crashes_or_falsely_verifies(self):
        # A flaky/faulty executor (raises, times out, or returns a malformed
        # result) must not crash the loop, and must never yield a verified pass.
        import subprocess
        def fix(model, prompt, timeout):
            return {'files': [{'path': 'calculator.py', 'content': 'def add(a, b):\n    return a + b\n'}]}
        faulty = {
            'raise': lambda *a, **k: (_ for _ in ()).throw(OSError('disk fail')),
            'timeout': lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired('cmd', 1)),
            'no_exit': lambda *a, **k: {'output': 'x'},
            'not_dict': lambda *a, **k: 'nope',
            'none': lambda *a, **k: None,
        }
        for name, runner in faulty.items():
            root = make_broken_demo(self.base / ('f_' + name))
            ev = self.base / ('fev_' + name)
            report = direct_repair(root, ev, max_repairs=2, generator=fix, runner=runner)  # must not raise
            self.assertNotEqual(report['status'], 'verified_direct_repair', name)

    def test_failed_patch_restores_source(self):
        original = (self.root / 'calculator.py').read_bytes()
        result = direct_repair(self.root, self.evidence, max_repairs=1,
            generator=lambda *a, **kw: {'files': [{'path': 'calculator.py', 'content': 'def add(a,b):\n    return 0\n'}]})
        self.assertEqual(result['status'], 'repair_failed')
        self.assertEqual((self.root / 'calculator.py').read_bytes(), original)

    def test_protected_edits_rejected(self):
        for name in ('test_calculator.py', '../evil.py', '/tmp/evil.py', 'nested/evil.py'):
            with self.subTest(name=name), self.assertRaises(SafetyError):
                apply_patch(self.root, {'files': [{'path': name, 'content': 'x=1'}]})

    def test_invalid_syntax_rejected_without_edit(self):
        original = (self.root / 'calculator.py').read_bytes()
        with self.assertRaises(SafetyError):
            apply_patch(self.root, {'files': [{'path': 'calculator.py', 'content': 'def broken('}]})
        self.assertEqual((self.root / 'calculator.py').read_bytes(), original)

    def test_no_cloud_endpoint(self):
        with self.assertRaises(SafetyError):
            request_patch('ollama/test', 'hi', endpoint='https://example.com')

    def test_http_protocol_fake_local_server(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                self.server.seen = (self.path, body)
                response = json.dumps({'response': json.dumps({'files':[{'path':'calculator.py','content':'def add(a,b):\n return a+b\n'}]})}).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(response)))
                self.end_headers()
                self.wfile.write(response)
            def log_message(self, *args):
                pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        # Substitute the fixed endpoint for an isolated loopback test server.
        with patch('adm.ollama_direct.DEFAULT_ENDPOINT', 'http://127.0.0.1:%d' % server.server_port):
            result = request_patch('ollama/test:latest', 'repair', endpoint='http://127.0.0.1:%d' % server.server_port)
        self.assertEqual(result['files'][0]['path'], 'calculator.py')
        self.assertEqual(server.seen[0], '/api/generate')
        self.assertFalse(server.seen[1]['stream'])
