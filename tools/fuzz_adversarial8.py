"""Adversarial harness, round 8: agent helpers, resource/size parsing, Unicode/locale edges."""
import os
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm import agent, model_selection, intake, queued_ai

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


def reject(label, fn):
    try:
        fn(); BUGS.append(f'[{label}] accepted bad input (expected reject)')
    except GRACEFUL:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] uncaught {type(exc).__name__}: {str(exc)[:160]}')


def pass_model_names():
    for m in ['ollama/../../x', 'ollama/a b', 'ollama/a;rm', 'ollama/\x00', 'ollama/' + 'a' * 5000,
              '', None, 42, 'ollama/модель', 'ollama/模型:7b', 'remote/x', 'local/x', 'OLLAMA/X',
              'ollama/a\nb', 'ollama/' + '🤖' * 50]:
        graceful('safe_local_model', lambda m=m: agent.safe_local_model(m))


def pass_sizes():
    for name in ['x', 'x:7b', 'x:3.5b', 'x:999999b', 'x:-5b', 'x:0b', 'модель:7b', 'a' * 10000 + ':7b',
                 'x:7B', 'x-13b-instruct', '7b', ':b', 'x:b', None, 42]:
        graceful('_size', lambda name=name: model_selection._size(name) if isinstance(name, str) else None)
    for models in [['a:7b'], ['модель:3b'], ['x' * 5000 + ':3b'], ['🤖:3b'], ['a:7b'] * 5000,
                   ['no-size'], ['x:999999b']]:
        graceful('select_installed_model', lambda models=models: model_selection.select_installed_model(models, ram_gib=16))


def pass_unicode_slug(base):
    for title in ['', 'tip calculator', 'СЧЁТ калькулятор', '模型计算器', '🤖🤖🤖', '  ...---...  ',
                  'a' * 10000, 'CON', 'app.py', '../escape', 'a/b\\c', 'tab\ttab', 'null\x00here']:
        def run(title=title):
            slug = intake.slugify(title)
            # a slug must be a safe single path segment
            assert isinstance(slug, str) and slug and '/' not in slug and '\\' not in slug and '\x00' not in slug
            assert '..' not in Path(slug).parts
        graceful(f'slugify[{title[:10]!r}]', run)
    # a plan with a hostile unicode title must produce a usable folder
    home = base / 'uhome'; home.mkdir(); state = base / 'ustate'
    ans = {'title': '../../模型 \x00 🤖', 'summary': 's', 'features': ['f'], 'tests': ['t'],
           'needs_internet': False, 'questions': []}
    graceful('create_plan_unicode_title', lambda: intake.approve(intake.create_plan(
        state, 'a unicode titled tool', mode='new', folder='',
        generator=lambda m, p, t: ans, model='ollama/x', home=home)['path']))


def pass_validate_project(base):
    root = base / 'vp'; root.mkdir()
    graceful('validate_missing', lambda: agent.validate_project(root, base / 'vev'))
    (root / 'requirements.json').write_text('{}')
    (root / 'test_app.py').write_text('import unittest')
    (root / 'app.py').write_text('x=1')
    graceful('validate_ok', lambda: agent.validate_project(root, base / 'vev2'))
    if hasattr(os, 'symlink'):
        try:
            os.symlink(base / 'target', root / 'link.py')
            reject('validate_symlink', lambda: agent.validate_project(root, base / 'vev3'))
        except OSError:
            pass
    # evidence inside the project must be refused
    reject('validate_evidence_inside', lambda: agent.validate_project(root, root / 'inside'))


def pass_misc(base):
    graceful('physical_ram_gib', lambda: queued_ai.physical_ram_gib())
    for args in [('', '', 0), ('r' * 100000, 'f' * 100000, -5), ('x', 'y', 10 ** 9)]:
        graceful('make_prompt', lambda args=args: agent.make_prompt(*args))
    # atomic_json with un-serialisable / huge values
    graceful('atomic_json_bad', lambda: agent.atomic_json(base / 'aj.json', {'x': object()}))
    graceful('atomic_json_ok', lambda: agent.atomic_json(base / 'aj2.json', {'x': [1, 2, 3]}))
    # run_agent with a fake executable that spews garbage then exits (timeout-protected)
    if os.name != 'nt':
        script = base / 'fakeagent.sh'
        script.write_text('#!/bin/sh\nprintf "garbage \\xff\\xfe\\n"\nexit 3\n')
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        proj = base / 'ap'; proj.mkdir(); (proj / 'app.py').write_text('x=1')
        graceful('run_agent_fake', lambda: agent.run_agent(proj, 'ollama/x', 'prompt', [str(script)], timeout=20))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_model_names()
        pass_sizes()
        pass_unicode_slug(base)
        pass_validate_project(base)
        pass_misc(base)
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
