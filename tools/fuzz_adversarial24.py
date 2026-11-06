"""Adversarial harness, round 24: model_probe local-inference parsing against a
hostile (injected) Ollama opener — malformed/oversized/wrong-type responses,
redirects, and the public installed_models/_request/smoke_test/benchmark_report.
No real network is used."""
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm import model_probe
from adm.setup import MODELS

BUGS = []
OK = [0]
MODEL = list(MODELS.values())[0]


def no_raise(label, fn):
    try:
        fn(); OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] raised {type(exc).__name__}: {str(exc)[:140]}')


def graceful(label, fn, allowed):
    try:
        fn(); OK[0] += 1
    except allowed:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] unexpected {type(exc).__name__}: {str(exc)[:140]}')


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self
    def __exit__(self, *a):
        self.close()
        return False


def opener_returning(payloads):
    """Return an opener callable that yields the next payload (bytes or a
    callable producing a response object) on each call."""
    seq = iter(payloads)

    def _opener(req, timeout=None):
        try:
            item = next(seq)
        except StopIteration:
            item = b'{}'
        if callable(item):
            return item()
        if isinstance(item, Exception):
            raise item
        return FakeResp(item if isinstance(item, bytes) else str(item).encode('utf-8'))
    return _opener


def pass_smoke_hostile():
    # smoke_test must ALWAYS return a ProbeResult, never raise, whatever the
    # (fake) server returns for /api/tags then /api/generate.
    tags_ok = json.dumps({'models': [{'name': MODEL}]}).encode('utf-8')
    hostile_generate = [
        b'not json', b'', b'[]', b'"str"', b'42', b'null',
        json.dumps({'done': False}).encode(),
        json.dumps({'done': True, 'response': 123}).encode(),
        json.dumps({'done': True, 'response': 'READY'}).encode(),
        json.dumps({'done': True, 'response': 'nope'}).encode(),
        b'{' * 100000,                                   # deeply broken
        b'x' * (model_probe.MAX_RESPONSE + 10),          # oversize
        lambda: FakeResp(b'\x00\x01\x02'),               # binary junk
    ]
    for i, gen in enumerate(hostile_generate):
        op = opener_returning([tags_ok, gen])
        no_raise(f'smoke_test[{i}]', lambda op=op: model_probe.smoke_test(MODEL, timeout=5, opener=op))
    # hostile /api/tags responses too
    for i, tags in enumerate([b'not json', b'{}', json.dumps({'models': 'x'}).encode(),
                              json.dumps({'models': [1, 2, 3]}).encode(),
                              json.dumps({'models': [{'noname': 1}]}).encode()]):
        op = opener_returning([tags, b'{}'])
        no_raise(f'smoke_test_tags[{i}]', lambda op=op: model_probe.smoke_test(MODEL, timeout=5, opener=op))


def pass_installed_models():
    # installed_models raises ValueError on a bad shape (documented), never
    # something unhandled; valid shape returns names.
    graceful('installed_models_badshape',
             lambda: model_probe.installed_models(opener=opener_returning([b'{"models": "x"}'])), ValueError)
    names = model_probe.installed_models(opener=opener_returning([json.dumps({'models': [{'name': 'a'}, {'noname': 1}]}).encode()]))
    OK[0] += 1 if names == ['a'] else BUGS.append(f'[installed_models_valid] {names}')


def pass_request_guards():
    graceful('request_bad_timeout',
             lambda: model_probe._request('/x', None, 0, opener_returning([b'{}'])), ValueError)
    graceful('request_oversize',
             lambda: model_probe._request('/x', None, 5, opener_returning([b'x' * (model_probe.MAX_RESPONSE + 10)])), ValueError)
    graceful('request_nondict',
             lambda: model_probe._request('/x', None, 5, opener_returning([b'[1,2,3]'])), ValueError)


def pass_benchmark():
    graceful('benchmark_dupes', lambda: model_probe.benchmark_report([MODEL, MODEL]), ValueError)
    graceful('benchmark_unapproved', lambda: model_probe.benchmark_report(['evil/model']), ValueError)
    op = opener_returning([json.dumps({'models': [{'name': MODEL}]}).encode(),
                           json.dumps({'done': True, 'response': 'READY'}).encode()])
    no_raise('benchmark_ok', lambda: model_probe.benchmark_report([MODEL], opener=op))
    graceful('smoke_unapproved', lambda: model_probe.smoke_test('evil/model'), ValueError)


def main():
    pass_smoke_hostile()
    pass_installed_models()
    pass_request_guards()
    pass_benchmark()
    print(f'round24: {OK[0]} checks ok, {len(BUGS)} bugs')
    for b in BUGS:
        print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
