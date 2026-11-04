"""Regression tests ensuring local AI transport never follows redirects."""
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from adm.engine import SafetyError
from adm.ollama_direct import request_patch
from adm.model_probe import installed_models


class RedirectHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(302)
        self.send_header('Location', 'https://example.com/collect')
        self.end_headers()
    def do_GET(self):
        self.send_response(302)
        self.send_header('Location', 'https://example.com/collect')
        self.end_headers()
    def log_message(self, *args):
        pass


class LocalTransportSecurityTests(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(('127.0.0.1', 0), RedirectHandler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def test_patch_request_refuses_redirect(self):
        endpoint = 'http://127.0.0.1:%d' % self.server.server_port
        with self.assertRaises(SafetyError):
            request_patch('ollama/test:latest', 'private source', endpoint=endpoint, timeout=2)

    def test_model_probe_refuses_redirect(self):
        from unittest.mock import patch
        with patch('adm.model_probe.BASE', 'http://127.0.0.1:%d' % self.server.server_port):
            with self.assertRaises(ValueError):
                installed_models(timeout=2)
