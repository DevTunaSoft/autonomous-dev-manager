"""Adversarial harness, round 5: hostile model-server HTTP responses. A fake local server returns
malformed / oversized / wrong-shape / error / redirect responses; the client code must fail
gracefully (SafetyError), never crash, hang, or exhaust memory. Exit 0 = clean."""
import sys
import threading
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm import backends, ollama_health
from adm.ollama_direct import request_json

BUGS = []
OK = [0]
GRACEFUL = (SafetyError, ValueError)


def graceful(label, fn):
    try:
        fn(); OK[0] += 1
    except GRACEFUL:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] uncaught {type(exc).__name__}: {str(exc)[:160]}')


def serve(status, body, *, redirect=False):
    data = body.encode('utf-8', 'replace') if isinstance(body, str) else body

    class H(BaseHTTPRequestHandler):
        def _reply(self):
            if redirect:
                self.send_response(302)
                self.send_header('Location', 'http://127.0.0.1:1/evil')
                self.end_headers()
                return
            self.send_response(status)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            self._reply()

        def do_POST(self):
            try:
                self.rfile.read(int(self.headers.get('Content-Length', 0)))
            except Exception:
                pass
            self._reply()

        def log_message(self, *a):
            pass

    srv = HTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


DEEP = ('[' * 2000) + '1' + (']' * 2000)
HUGE = '{"x":"' + 'a' * 2_000_000 + '"}'

CASES = [
    (200, 'not json at all'),
    (200, '[]'),
    (200, 'null'),
    (200, '{}'),
    (200, '123'),
    (200, '{"models": "notalist"}'),
    (200, '{"models": [{"noname": 1}]}'),
    (200, '{"models": [{"name": ""}]}'),
    (200, '{"models": [{"name": 123}]}'),
    (200, '{"choices": []}'),
    (200, '{"choices": [{"message": {}}]}'),
    (200, '{"choices": [{"message": {"content": "here you go, not json"}}]}'),
    (200, '{"response": 123}'),
    (200, '{"response": "not json patch"}'),
    (200, '{"data": "notlist"}'),
    (200, DEEP),
    (200, HUGE),
    (500, '{"error": "server boom"}'),
    (404, 'nope'),
    (400, '{"error":"bad request"}'),
]


def run_all(label, call):
    for status, body in CASES:
        srv = serve(status, body)
        endpoint = 'http://127.0.0.1:%d' % srv.server_port
        try:
            graceful(f'{label}[{status}:{body[:12]}]', lambda e=endpoint: call(e))
        finally:
            srv.shutdown(); srv.server_close()
    # redirect case
    srv = serve(200, '{}', redirect=True)
    endpoint = 'http://127.0.0.1:%d' % srv.server_port
    try:
        graceful(f'{label}[redirect]', lambda: call(endpoint))
    finally:
        srv.shutdown(); srv.server_close()


def main():
    run_all('inspect_ollama', lambda e: ollama_health.inspect_ollama(endpoint=e, timeout=5))
    run_all('request_json_ollama', lambda e: request_json('ollama/x', 'p', endpoint=e, timeout=5))
    run_all('request_json_openai', lambda e: backends.request_json_openai('local/x', 'p', endpoint=e, timeout=5))
    run_all('probe_local_servers', lambda e: backends.probe_local_servers(
        {'fake': int(e.rsplit(':', 1)[1])}, timeout=2))
    print(f'checks passed: {OK[0]}')
    if BUGS:
        print(f'\nBUGS FOUND: {len(BUGS)}')
        for b in BUGS:
            print('  -', b)
        return 1
    print('No crashes or corruption found.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
