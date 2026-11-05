"""Adversarial harness, round 17: the AI backend surface — extract_json on
hostile/garbled model text, safe_model identifier validation, and the
generator factories' config validation. No real network is touched."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm import backends

BUGS = []
OK = [0]


def graceful(label, fn):
    try:
        fn(); OK[0] += 1
    except SafetyError:
        OK[0] += 1
    except (ValueError, TypeError, OSError, RecursionError) as exc:
        BUGS.append(f'[{label}] unhandled {type(exc).__name__} (want SafetyError): {str(exc)[:120]}')
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] uncaught {type(exc).__name__}: {str(exc)[:140]}')


def no_raise(label, fn):
    try:
        fn(); OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] raised {type(exc).__name__}: {str(exc)[:140]}')


def returns_json(label, text, expect):
    try:
        got = backends.extract_json(text)
        OK[0] += 1 if got == expect else BUGS.append(f'[{label}] got {got!r} expected {expect!r}')
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] raised {type(exc).__name__}: {str(exc)[:120]}')


def pass_extract_json_graceful():
    # Garbage input must raise SafetyError (handled), never crash.
    bad = [None, '', '   ', 42, [], {}, 'no json here', '{', '[', '{"a":', '}{',
           '{"a": 1', '```json\n', '```\n```', '{' * 5000, '[' * 5000,
           '{"a": "unterminated', '\x00\x01\x02', '{"a": 1,,,}', 'nan', 'Infinity']
    for i, t in enumerate(bad):
        graceful(f'extract_json_bad[{i}]', lambda t=t: backends.extract_json(t))


def pass_extract_json_recovers():
    # Forgiving about WRAPPING only — these should parse to the embedded value.
    returns_json('fenced', '```json\n{"a": 1}\n```', {'a': 1})
    returns_json('prose_wrapped', 'Sure! Here you go: {"files": []} hope it helps', {'files': []})
    returns_json('trailing_comma', '{"a": 1, "b": [1, 2,],}', {'a': 1, 'b': [1, 2]})
    returns_json('array', '[1, 2, 3]', [1, 2, 3])
    returns_json('braces_in_string', '{"msg": "a } ] { [ b"}', {'msg': 'a } ] { [ b'})
    returns_json('plain', '{"x": true}', {'x': True})


def pass_safe_model():
    bad = [None, 42, '', 'noslash', 'bogus/name', 'remote/x', 'ollama/',
           'ollama/..', 'ollama//etc', 'ollama/.hidden', 'ollama/' + 'a' * 200,
           'ollama/bad name', 'ollama/semi;colon', 'local/$(rm -rf)', 'ollama/a\x00b']
    for m in bad:
        graceful(f'safe_model[{str(m)[:16]!r}]', lambda m=m: backends.safe_model(m))
    # valid identifiers pass
    for m, kind in [('ollama/llama3', 'ollama'), ('local/qwen2.5-coder:3b', 'local'),
                    ('ollama/org/model', 'ollama')]:
        try:
            k, _ = backends.safe_model(m)
            OK[0] += 1 if k == kind else BUGS.append(f'[safe_model_valid[{m}]] kind {k}')
        except BaseException as exc:          # noqa: BLE001
            BUGS.append(f'[safe_model_valid[{m}]] raised {type(exc).__name__}: {exc}')
    # remote requires approval; with allow_remote it is accepted
    graceful('safe_model_remote_denied', lambda: backends.safe_model('remote/gpt'))
    no_raise('safe_model_remote_allowed', lambda: backends.safe_model('remote/gpt', allow_remote=True))


def pass_factories():
    # Building a generator validates the model id and config; a bad id must raise
    # SafetyError at construction (no network call needed).
    for m in [None, 'noslash', 'remote/x', 'ollama/..']:
        graceful(f'make_generator[{str(m)[:12]!r}]', lambda m=m: backends.make_generator(m))
        graceful(f'make_json_generator[{str(m)[:12]!r}]', lambda m=m: backends.make_json_generator(m))
    # valid local model builds a callable without touching the network
    no_raise('make_generator_ok', lambda: backends.make_generator('ollama/llama3'))
    no_raise('make_json_generator_ok', lambda: backends.make_json_generator('ollama/llama3'))


def pass_probe():
    # probe_local_servers must tolerate a hostile/empty ports map without raising
    # (it may return []). It attempts loopback connects only.
    for ports in [None, {}, {'bad': 'notint'}, {11434: 'name'}, {99999: 'x'}]:
        no_raise(f'probe[{ports!r:.20}]', lambda ports=ports: backends.probe_local_servers(ports, timeout=0.05))


def main():
    pass_extract_json_graceful()
    pass_extract_json_recovers()
    pass_safe_model()
    pass_factories()
    pass_probe()
    print(f'round17: {OK[0]} checks ok, {len(BUGS)} bugs')
    for b in BUGS:
        print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
