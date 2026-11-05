"""Adversarial harness, round 6: release/archive handling (incl. zip bombs & traversal),
the provisioning plan validator, the pipeline spec, model_probe HTTP, and context budget math."""
import io
import json
import sys
import tempfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm import release, provision, pipeline, model_probe, context, repomap

BUGS = []
OK = [0]
GRACEFUL = (SafetyError, ValueError, PermissionError, OSError)


def graceful(label, fn):
    try:
        fn(); OK[0] += 1
    except GRACEFUL:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] uncaught {type(exc).__name__}: {str(exc)[:160]}')


def _zip(entries: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return buf.getvalue()


def pass_release(base):
    cases = {
        'not_a_zip': b'this is not a zip file',
        'empty_zip': _zip({}),
        'no_manifest': _zip({'ADM/app.py': 'x=1'}),
        'manifest_not_json': _zip({'ADM/SOURCE-MANIFEST.json': 'not json'}),
        'manifest_array': _zip({'ADM/SOURCE-MANIFEST.json': '[]'}),
        'manifest_no_files': _zip({'ADM/SOURCE-MANIFEST.json': '{"files": "x"}'}),
        'manifest_bad_entries': _zip({'ADM/SOURCE-MANIFEST.json': '{"files": {"a.py": 123}}'}),
        'name_mismatch': _zip({'ADM/SOURCE-MANIFEST.json': '{"files": {"a.py": "deadbeef"}}'}),
        'traversal': _zip({'ADM/SOURCE-MANIFEST.json': '{"files": {"../evil.py": "x"}}',
                           'ADM/../evil.py': 'x=1'}),
        'backslash': _zip({'ADM/SOURCE-MANIFEST.json': '{"files": {"a\\\\b.py": "x"}}'}),
        'hash_mismatch': _zip({'ADM/SOURCE-MANIFEST.json': '{"files": {"a.py": "00"}}', 'ADM/a.py': 'x=1'}),
        'zip_bomb': _zip({'ADM/SOURCE-MANIFEST.json': '{"files": {"big.py": "00"}}',
                          'ADM/big.py': 'A' * (80 * 1024 * 1024)}),       # ~80MB uncompressed, tiny compressed
        'deep_manifest': _zip({'ADM/SOURCE-MANIFEST.json': '{"files":' + '[' * 3000 + ']' * 3000 + '}'}),
    }
    for label, data in cases.items():
        p = base / f'{label}.zip'
        p.write_bytes(data)
        graceful(f'verify_release[{label}]', lambda p=p: release.verify_source_release(p))
    graceful('create_release_missing_root', lambda: release.create_source_release(base / 'nope', base / 'o.zip'))
    f = base / 'afile'; f.write_text('x')
    graceful('create_release_root_is_file', lambda: release.create_source_release(f, base / 'o2.zip'))


def pass_provision(base):
    calls = []
    def fake_executor(step):
        calls.append(step); return {'status': 'ok'}
    bad_plans = [None, {}, [], 'x', {'platform': 'Linux'}, {'platform': 'Windows'},
                 {'platform': 'Windows', 'steps': 'x'}, {'platform': 'Windows', 'steps': [1, 2]},
                 {'platform': 'Windows', 'steps': [{'key': 'evil'}]},
                 {'platform': 'Windows', 'steps': [{'key': 'pull_model'}, {'key': 'pull_model'}]}]
    for i, plan in enumerate(bad_plans):
        graceful(f'execute_plan_unapproved[{i}]', lambda plan=plan: provision.execute_plan(plan, base / f'j{i}.json'))
        graceful(f'execute_plan[{i}]', lambda plan=plan, i=i:
                 provision.execute_plan(plan, base / f'k{i}.json', approved=True, executor=fake_executor))
    # corrupt journal on resume
    jp = base / 'corruptj.json'; jp.write_text('{ not json')
    good = {'platform': 'Windows', 'steps': [{'key': 'install_ollama'}]}
    graceful('execute_plan_corrupt_journal', lambda: provision.execute_plan(good, jp, approved=True, executor=fake_executor))


def pass_pipeline(base):
    for state in [base / 'nostate', base / 'empty']:
        state.mkdir(exist_ok=True)
        graceful('run_pipeline_missing', lambda state=state: pipeline.run_pipeline(state, timeout=5))
    sd = base / 'badspec'; sd.mkdir()
    (sd / 'pipeline.json').write_text('not json')
    graceful('run_pipeline_badspec', lambda: pipeline.run_pipeline(sd, timeout=5))
    (sd / 'pipeline.json').write_text('[]')
    graceful('run_pipeline_arrayspec', lambda: pipeline.run_pipeline(sd, timeout=5))


def _server(status, body):
    data = body.encode() if isinstance(body, str) else body

    class H(BaseHTTPRequestHandler):
        def _send(self):
            try:
                self.send_response(status); self.send_header('Content-Length', str(len(data)))
                self.end_headers(); self.wfile.write(data)
            except OSError:
                pass
        def do_GET(self):
            self._send()
        def do_POST(self):
            try:
                self.rfile.read(int(self.headers.get('Content-Length', 0)))
            except Exception:
                pass
            self._send()
        def log_message(self, *a):
            pass
    srv = HTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _fixed_opener(base_url):
    """A callable (req, timeout) -> response that redirects to our fake server, matching _safe_open."""
    import urllib.request
    real = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def opener(req, timeout=None):
        path = req.selector if hasattr(req, 'selector') else getattr(req, 'full_url', '')
        if path.startswith('http'):
            from urllib.parse import urlsplit
            path = urlsplit(path).path
        return real.open(base_url + path, timeout=timeout)
    return opener


def pass_model_probe():
    from adm.model_probe import MODELS
    a_model = next(iter(MODELS.values()))
    bodies = ['not json', '[]', 'null', '{}', '{"models":"x"}', '{"models":[{"noname":1}]}',
              '{"data":[{"id":123}]}', '{"response":123}', ('[' * 2000 + '1' + ']' * 2000),
              '{"x":"' + 'a' * 2_000_000 + '"}']
    for body in bodies:
        for status in (200, 500):
            srv = _server(status, body)
            base_url = 'http://127.0.0.1:%d' % srv.server_port
            try:
                op = _fixed_opener(base_url)
                graceful(f'installed_models[{status}:{body[:8]}]',
                         lambda op=op: model_probe.installed_models(timeout=3, opener=op))
                # smoke_test must NEVER raise -- it returns a ProbeResult even on hostile responses
                graceful(f'smoke_test[{status}:{body[:8]}]',
                         lambda op=op: model_probe.smoke_test(a_model, timeout=3, opener=op))
            finally:
                srv.shutdown(); srv.server_close()


def pass_context():
    big = 'FAILED x::y\n' * 20000
    for budget in [-100, 0, 1, 5, 10 ** 9]:
        root = Path(tempfile.mkdtemp())
        (root / 'app.py').write_text('x = 1\n')
        (root / 'test_app.py').write_text('import unittest\nfrom app import x\n')
        graceful(f'select_context[{budget}]', lambda root=root, budget=budget: repomap.select_context(root, big, budget))
    for args in [('', '', 0), ('r' * 100000, 'f' * 100000, 1), ('x', 'y', -5), ('a', 'b', 10 ** 9)]:
        graceful('build_repair_prompt', lambda args=args: context.build_repair_prompt(args[0], args[1], args[2], 'ctx', ''))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_release(base)
        pass_provision(base)
        pass_pipeline(base)
        pass_model_probe()
        pass_context()
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
