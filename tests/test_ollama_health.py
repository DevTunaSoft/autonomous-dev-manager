import json
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from adm.engine import SafetyError
from adm.ollama_health import inspect_ollama, main


class HealthTests(unittest.TestCase):
    def server(self, status=200, payload=None, redirect=None):
        payload = payload if payload is not None else {'models': [{'name': 'qwen2.5-coder:3b'}]}
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.path_seen = self.path
                self.send_response(302 if redirect else status)
                if redirect:
                    self.send_header('Location', redirect)
                body = json.dumps(payload).encode()
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server, f'http://127.0.0.1:{server.server_port}'

    def test_list_installed_models(self):
        server, url = self.server(payload={'models': [{'name': 'z:1'}, {'name': 'a:2'}, {'name': 'z:1'}]})
        result = inspect_ollama(endpoint=url)
        self.assertEqual(result['installed_models'], ['a:2', 'z:1'])
        self.assertEqual(result['model_count'], 2)
        self.assertFalse(result['inference_verified'])
        self.assertEqual(server.path_seen, '/api/tags')

    def test_reject_remote_and_non_loopback(self):
        for endpoint in ['https://127.0.0.1:11434', 'http://localhost:11434',
                         'http://8.8.8.8:11434', 'http://127.0.0.1:11434/other',
                         'http://127.0.0.1:11434?x=1']:
            with self.subTest(endpoint=endpoint), self.assertRaises(SafetyError):
                inspect_ollama(endpoint=endpoint)

    def test_redirect_never_followed(self):
        _, url = self.server(redirect='https://example.com/collect')
        with self.assertRaises(SafetyError):
            inspect_ollama(endpoint=url)

    def test_invalid_metadata_rejected(self):
        _, url = self.server(payload={'models': 'wrong'})
        with self.assertRaises(SafetyError):
            inspect_ollama(endpoint=url)

    def test_unavailable_server_reports_error(self):
        server, url = self.server()
        server.shutdown()
        server.server_close()
        with self.assertRaises(SafetyError):
            inspect_ollama(endpoint=url, timeout=0.3)

    def test_invalid_timeout(self):
        with self.assertRaises(SafetyError):
            inspect_ollama(timeout=40)

    def test_cli_returns_failure_without_server(self):
        self.assertEqual(main(['--endpoint', 'http://127.0.0.1:1']), 1)
