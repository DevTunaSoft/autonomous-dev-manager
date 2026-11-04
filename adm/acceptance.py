"""Offline end-to-end acceptance: real HTTP transport and subprocess tests, fake AI.

This validates the plumbing without claiming real local-model inference. The fixture
server binds only to loopback and is shut down even on assertion failures.
"""
from __future__ import annotations
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
from threading import Thread
from .engine import make_broken_demo, SafetyError
from .ollama_direct import direct_repair, request_patch


class _FixtureHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/api/generate':
            self.send_error(404)
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 150_000:
                self.send_error(413)
                return
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict) or body.get('stream') is not False or 'calculator.py' not in body.get('prompt', ''):
                self.send_error(400)
                return
            self.server.requests_seen += 1
            response = {'response': json.dumps({'files': [
                {'path': 'calculator.py', 'content': 'def add(a, b):\n    return a + b\n'}]})}
            payload = json.dumps(response).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (ValueError, TypeError, OSError):
            self.send_error(400)

    def log_message(self, *_args):
        pass


def run_offline_acceptance(output_dir: str | Path) -> dict:
    """Produce a durable evidence report. No installed Ollama or network required."""
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise SafetyError('Acceptance output must be an empty directory')
    root = make_broken_demo(output / 'demo-project')
    evidence = output / 'evidence'
    server = ThreadingHTTPServer(('127.0.0.1', 0), _FixtureHandler)
    server.requests_seen = 0
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = f'http://127.0.0.1:{server.server_port}'
        def generator(model, prompt, timeout):
            return request_patch(model, prompt, endpoint=endpoint, timeout=timeout)
        report = direct_repair(root, evidence, model='ollama/acceptance-fixture',
                               max_repairs=1, timeout=30, generator=generator)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    success = (report['status'] == 'verified_direct_repair' and
               report['baseline']['exit_code'] != 0 and
               report['attempts'][0]['test']['exit_code'] == 0 and
               server.requests_seen == 1 and not report['live_model_verified'] and
               not (evidence / 'repair-journal.json').exists())
    summary = {'passed': bool(success), 'transport': 'real loopback HTTP',
               'model': 'deterministic fixture, NOT a real AI',
               'real_model_verified': False, 'requests_seen': server.requests_seen,
               'baseline_exit': report['baseline']['exit_code'],
               'repair_status': report['status'],
               'post_repair_exit': report['attempts'][0]['test']['exit_code'] if report['attempts'] else None,
               'report': str(evidence / 'ollama-direct-report.json')}
    (output / 'acceptance-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run offline AI repair plumbing acceptance')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    summary = run_offline_acceptance(args.output)
    print(json.dumps(summary, indent=2))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
