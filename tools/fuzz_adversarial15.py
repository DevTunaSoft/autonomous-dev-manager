"""Adversarial harness, round 15: intake plan rendering and parsing — plan_text
on corrupt/partial on-disk plans, parse_plan on hostile model output, and
load_plan/require_approved integrity under tampering."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm import intake

BUGS = []
OK = [0]


def graceful(label, fn):
    try:
        fn(); OK[0] += 1
    except SafetyError:
        OK[0] += 1
    except (ValueError, TypeError, OSError) as exc:
        BUGS.append(f'[{label}] unhandled {type(exc).__name__} (want SafetyError): {str(exc)[:120]}')
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] uncaught {type(exc).__name__}: {str(exc)[:140]}')


def no_raise(label, fn):
    try:
        fn(); OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] raised {type(exc).__name__}: {str(exc)[:140]}')


def pass_parse_plan():
    bad = [None, [], 'x', 42, {}, {'title': 'T'}, {'summary': 'S'},
           {'title': '', 'summary': 'S'}, {'title': 'T', 'summary': ''},
           {'title': 123, 'summary': 'S'}, {'title': 'T', 'summary': 'S', 'features': 'notlist'},
           {'title': 'T', 'summary': 'S', 'tests': [1, 2, 3]},
           {'title': 'T', 'summary': 'S', 'questions': {'a': 1}},
           {'title': 'T', 'summary': 'S', 'needs_internet': 'yes'}]
    for i, a in enumerate(bad):
        graceful(f'parse_plan[{i}]', lambda a=a: intake.parse_plan(a))
    # a valid answer parses and is fully normalised
    good = intake.parse_plan({'title': 'T', 'summary': 'S', 'features': ['f'], 'tests': ['t']})
    for k in ('title', 'summary', 'features', 'tests', 'needs_internet', 'questions'):
        if k not in good:
            BUGS.append(f'[parse_plan_good] normalised content missing {k}')
            break
    else:
        OK[0] += 1


def pass_plan_text():
    # plan_text renders a plan in the GUI. A corrupt/partial plan.json that still
    # parses as a dict must not crash the renderer.
    partial = [
        {}, {'content': None}, {'content': {}}, {'content': 'x'},
        {'content': {'title': 'T'}},                       # missing most fields
        {'content': {'title': 'T', 'summary': 'S'}},       # missing lists/flags
        {'content': {'title': 'T', 'summary': 'S', 'features': None, 'tests': None,
                     'needs_internet': False, 'questions': None}},
        {'content': {'title': 'T', 'summary': 'S', 'features': [], 'tests': [],
                     'needs_internet': False, 'questions': []}},   # no folder/mode/status
    ]
    for i, p in enumerate(partial):
        no_raise(f'plan_text[{i}]', lambda p=p: intake.plan_text(p))
    # a fully well-formed plan renders and includes the title
    full = {'content': {'title': 'Calc', 'summary': 'Adds numbers', 'features': ['add'],
                        'tests': ['adds two numbers'], 'needs_internet': False, 'questions': []},
            'mode': 'new', 'status': 'approved', 'folder': '/tmp/x'}
    try:
        txt = intake.plan_text(full)
        OK[0] += 1 if 'Calc' in txt else BUGS.append('[plan_text_full] title missing')
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[plan_text_full] raised {type(exc).__name__}: {exc}')


def pass_load_and_verify(base):
    d = base / 'plans' / 'p1'
    d.mkdir(parents=True, exist_ok=True)
    pj = d / 'plan.json'
    # not a dict / garbage / partial
    for content in ['[1,2,3]', 'garbage{', '"a string"', '42', '{}']:
        pj.write_text(content, encoding='utf-8')
        graceful(f'load_plan[{content[:6]!r}]', lambda: intake.load_plan(pj))
        graceful(f'require_approved[{content[:6]!r}]', lambda: intake.require_approved(pj))
    # a dict missing body keys -> require_approved must reject via digest, not crash
    pj.write_text(json.dumps({'status': 'approved', 'content': {}}), encoding='utf-8')
    graceful('require_approved_no_digest', lambda: intake.require_approved(pj))
    # a tampered plan: valid-looking but wrong sha256
    pj.write_text(json.dumps({'request': 'r', 'mode': 'new', 'folder': '/f', 'model': 'm',
                              'content': {'title': 'T'}, 'sha256': 'deadbeef', 'status': 'approved'}),
                  encoding='utf-8')
    graceful('require_approved_tampered', lambda: intake.require_approved(pj))


def pass_validate_request():
    for r in ['', '   ', 'x', 'a' * 100000, '\x00\x01', 123, None, '\n\n\n', 'ok request here']:
        graceful(f'validate_request[{str(r)[:8]!r}]', lambda r=r: intake.validate_request(r))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_parse_plan()
        pass_plan_text()
        pass_load_and_verify(base)
        pass_validate_request()
    print(f'round15: {OK[0]} checks ok, {len(BUGS)} bugs')
    for b in BUGS:
        print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
