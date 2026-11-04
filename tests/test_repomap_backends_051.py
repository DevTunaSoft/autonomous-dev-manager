"""ADM-051: repo map, second local backend, escalation ladder."""
import json
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

from adm.backends import (safe_model, check_endpoint, request_patch_openai, make_generator,
                          probe_local_servers, parse_patch_text)
from adm.engine import SafetyError, make_broken_demo
from adm.ollama_direct import direct_repair
from adm.repomap import build_map, render_map, select_context, editable_files

GOOD = {'files': [{'path': 'calculator.py', 'content': 'def add(a, b):\n    return a + b\n'}]}


def serve(handler_cls):
    server = HTTPServer(('127.0.0.1', 0), handler_cls)
    Thread(target=server.serve_forever, daemon=True).start()
    return server


class RepoMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'app.py').write_text('import util\n\nclass Cart:\n    def total(self, items):\n        return sum(items)\n\ndef main():\n    pass\n')
        (self.root / 'util.py').write_text('def helper(x, *, y=1):\n    return x + y\n')
        (self.root / 'broken.py').write_text('def oops(:\n')
        (self.root / 'test_app.py').write_text('import unittest\nfrom app import Cart\n\nclass T(unittest.TestCase):\n    def test_t(self):\n        self.assertEqual(Cart().total([1]), 2)\n')
        (self.root / 'pkg').mkdir()
        (self.root / 'pkg' / 'inner.py').write_text('def deep(): pass\n')
        (self.root / '__pycache__').mkdir()
        (self.root / '__pycache__' / 'junk.py').write_text('x=1\n')

    def test_map_lists_symbols_signatures_and_parse_errors(self):
        text = render_map(build_map(self.root))
        self.assertIn('class Cart', text)
        self.assertIn('def total(self, items)', text)
        self.assertIn('def helper(x, *, y=1)', text)
        self.assertIn('does not parse', text)
        self.assertIn('pkg/inner.py', text)
        self.assertNotIn('junk.py', text)

    def test_only_toplevel_non_test_files_are_editable(self):
        self.assertEqual(editable_files(self.root), ['app.py', 'broken.py', 'util.py'])

    def test_failing_test_imports_decide_what_is_shown_in_full(self):
        failure = 'FAIL: test_t (test_app.T.test_t)\nAssertionError: 1 != 2\n'
        ctx = select_context(self.root, failure, budget_chars=2000)
        self.assertIn('app.py', ctx['full'])
        self.assertIn('FILE app.py (shown in full', ctx['text'])
        self.assertIn('NOT editable', ctx['text'])

    def test_unrelated_big_file_becomes_map_only_instead_of_blocking(self):
        (self.root / 'util.py').write_text('def helper():\n    return 1\n' + '# pad\n' * 3000)
        failure = 'FAIL: test_t (test_app.T.test_t)\n'
        ctx = select_context(self.root, failure, budget_chars=3000)
        self.assertIn('app.py', ctx['full'])
        self.assertNotIn('util.py', ctx['full'])
        self.assertIn('util.py', ctx['map_only'])

    def test_relevant_file_too_big_fails_closed(self):
        (self.root / 'app.py').write_text('class Cart:\n    pass\n' + '# pad\n' * 3000)
        with self.assertRaises(SafetyError) as raised:
            select_context(self.root, 'FAIL: test_t (test_app.T.test_t)\n', budget_chars=3000)
        self.assertIn('too large', str(raised.exception))


class BackendTests(unittest.TestCase):
    def test_model_ids(self):
        self.assertEqual(safe_model('ollama/qwen2.5-coder:3b'), ('ollama', 'qwen2.5-coder:3b'))
        self.assertEqual(safe_model('local/my-model')[0], 'local')
        for bad in ('qwen', 'cloud/x', 'local/', 'local/a b', 'remote/x'):
            with self.subTest(bad), self.assertRaises(SafetyError):
                safe_model(bad)
        self.assertEqual(safe_model('remote/x', allow_remote=True)[0], 'remote')

    def test_endpoints(self):
        self.assertEqual(check_endpoint('http://127.0.0.1:1337/'), 'http://127.0.0.1:1337')
        for bad in ('https://127.0.0.1:1337', 'http://localhost:1337', 'http://example.com:80',
                    'http://user:pw@127.0.0.1:1337', 'http://127.0.0.1:1337/v1', 'http://127.0.0.1'):
            with self.subTest(bad), self.assertRaises(SafetyError):
                check_endpoint(bad)
        check_endpoint('https://api.example.com', remote=True)
        for bad in ('http://api.example.com', 'https://u:p@api.example.com', 'https://a.com/x'):
            with self.subTest(bad), self.assertRaises(SafetyError):
                check_endpoint(bad, remote=True)

    def test_openai_compatible_roundtrip_and_fenced_json(self):
        seen = {}
        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                seen['path'], seen['body'], seen['auth'] = self.path, body, self.headers.get('Authorization')
                content = '```json\n' + json.dumps(GOOD) + '\n```'
                out = json.dumps({'choices': [{'message': {'content': content}}]}).encode()
                self.send_response(200); self.send_header('Content-Length', str(len(out))); self.end_headers()
                self.wfile.write(out)
            def log_message(self, *a): pass
        server = serve(H); self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        gen = make_generator('local/test-model', endpoint=f'http://127.0.0.1:{server.server_port}')
        self.assertTrue(gen.adm_live_generator)
        patch = gen('local/test-model', 'repair please', timeout=30)
        self.assertEqual(patch, GOOD)
        self.assertEqual(seen['path'], '/v1/chat/completions')
        self.assertEqual(seen['body']['model'], 'test-model')
        self.assertEqual(seen['body']['temperature'], 0)
        self.assertIsNone(seen['auth'])

    def test_retries_without_json_mode_when_server_rejects_it(self):
        calls = []
        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append('response_format' in body)
                if 'response_format' in body:
                    self.send_response(400); self.send_header('Content-Length', '0'); self.end_headers(); return
                out = json.dumps({'choices': [{'message': {'content': json.dumps(GOOD)}}]}).encode()
                self.send_response(200); self.send_header('Content-Length', str(len(out))); self.end_headers()
                self.wfile.write(out)
            def log_message(self, *a): pass
        server = serve(H); self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        patch = request_patch_openai('local/m', 'x', endpoint=f'http://127.0.0.1:{server.server_port}')
        self.assertEqual(patch, GOOD)
        self.assertEqual(calls, [True, False])

    def test_redirects_are_blocked(self):
        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(307); self.send_header('Location', 'http://example.com/'); self.send_header('Content-Length', '0'); self.end_headers()
            def log_message(self, *a): pass
        server = serve(H); self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        with self.assertRaises(SafetyError):
            request_patch_openai('local/m', 'x', endpoint=f'http://127.0.0.1:{server.server_port}')

    def test_remote_needs_consent_and_https(self):
        with self.assertRaises(SafetyError):
            make_generator('remote/m', endpoint='https://api.example.com')
        with self.assertRaises(SafetyError):
            make_generator('remote/m', endpoint='http://api.example.com', allow_remote=True)
        self.assertTrue(make_generator('remote/m', endpoint='https://api.example.com', allow_remote=True).adm_live_generator)

    def test_bad_envelopes_are_rejected(self):
        for text in ('not json', '[]', '{"files": "x"}', '{"files": [], "extra": 1}'):
            with self.subTest(text), self.assertRaises(SafetyError):
                parse_patch_text(text)

    def test_probe_finds_a_running_server_and_ignores_closed_ports(self):
        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                out = json.dumps({'data': [{'id': 'qwen-test'}]}).encode()
                self.send_response(200); self.send_header('Content-Length', str(len(out))); self.end_headers()
                self.wfile.write(out)
            def log_message(self, *a): pass
        server = serve(H); self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        found = probe_local_servers({'Fake': server.server_port, 'Closed': 1}, timeout=1)
        self.assertEqual([f['server'] for f in found], ['Fake'])
        self.assertEqual(found[0]['models'], ['qwen-test'])


class EscalationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = make_broken_demo(self.base / 'p')

    def test_escalates_after_failed_tries_and_tests_still_decide(self):
        used = []
        def small(model, prompt, timeout):
            used.append(model)
            return {'files': [{'path': 'calculator.py',
                               'content': f'def add(a, b):\n    return {len(used)}\n'}]}
        def big(model, prompt, timeout):
            used.append(model)
            return GOOD
        report = direct_repair(self.root, self.base / 'ev', max_repairs=3, generator=small,
                               escalation_model='ollama/bigger:7b', escalation_generator=big, escalate_after=2)
        self.assertEqual(used, ['ollama/qwen2.5-coder:3b', 'ollama/qwen2.5-coder:3b', 'ollama/bigger:7b'])
        self.assertEqual(report['status'], 'verified_direct_repair')
        self.assertTrue(report['escalation']['used'])
        self.assertEqual([a['generator'] for a in report['attempts']], ['primary', 'primary', 'escalation'])
        self.assertFalse(report['live_model_verified'])      # injected fakes are never "live"

    def test_no_escalation_configured_means_no_escalation(self):
        report = direct_repair(self.root, self.base / 'ev', max_repairs=2,
                               generator=lambda *a, **k: {'files': [{'path': 'calculator.py', 'content': 'def add(a,b):\n    return 9\n'}]})
        self.assertFalse(report['escalation']['configured'])
        self.assertFalse(report['escalation']['used'])

    def test_primary_model_cannot_be_remote_and_escalation_needs_a_name(self):
        with self.assertRaises(SafetyError):
            direct_repair(self.root, self.base / 'e1', model='remote/x', generator=lambda *a, **k: GOOD)
        with self.assertRaises(SafetyError):
            direct_repair(self.root, self.base / 'e2', escalation_generator=lambda *a, **k: GOOD)

    def test_local_openai_model_can_be_primary(self):
        report = direct_repair(self.root, self.base / 'ev', model='local/any', generator=lambda *a, **k: GOOD)
        self.assertEqual(report['status'], 'verified_direct_repair')


if __name__ == '__main__':
    unittest.main()
