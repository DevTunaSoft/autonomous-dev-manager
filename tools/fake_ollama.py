"""FAKE Ollama for packaged-plumbing tests. Not a model: always returns one canned patch.

Serves /api/tags and /api/generate on 127.0.0.1:11434. Evidence produced against
this server proves the EXE's plumbing only; it says nothing about real inference.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PATCH = {'files': [{'path': 'calculator.py', 'content': 'def add(a, b):\n    return a + b\n'}]}


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send({'models': [{'name': 'qwen2.5-coder:3b'}]})

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', 0)))
        self._send({'response': json.dumps(PATCH), 'done': True})

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    HTTPServer(('127.0.0.1', int(sys.argv[1]) if len(sys.argv) > 1 else 11434), Handler).serve_forever()
