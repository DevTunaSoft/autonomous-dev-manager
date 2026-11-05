"""Adversarial harness, round 10: the packaging stage (entry generation, exe
names, hostile plans) plus diagnostics self-check under hostile state. New
surface added by the Package & deliver stage."""
import ast
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm import package, diagnostics

BUGS = []
OK = [0]
GRACEFUL = (SafetyError, ValueError, PermissionError, OSError, TypeError)


def graceful(label, fn):
    try:
        fn(); OK[0] += 1
    except GRACEFUL:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] uncaught {type(exc).__name__}: {str(exc)[:160]}')


def check(label, cond):
    if cond:
        OK[0] += 1
    else:
        BUGS.append(f'[{label}] assertion failed')


def pass_exe_name():
    for title in ['', '   ', '!!!', None, 123, 'A' * 500, 'My App 2.0',
                  '../../etc', 'café ☕ app', '\x00\x01', '-----', '  --x--  ']:
        graceful(f'exe_name[{title!r:.20}]', lambda title=title: package.exe_name(title))
    # must always yield a safe, non-empty, bounded slug
    for title in ['', None, '!!!', '../../x', 'A' * 500]:
        name = package.exe_name(title)
        check(f'exe_name_safe[{title!r:.20}]',
              isinstance(name, str) and 0 < len(name) <= 40
              and all(c.isalnum() or c == '-' for c in name))


def pass_write_entry(base):
    # Hostile titles: the generated main.py must still be valid Python.
    titles = [
        'back\\slash', 'ends with backslash\\', r'C:\Users\x',
        'quote"inside', 'triple"""quote', 'new\nline', 'tab\there',
        'APP_EXE', 'APP_TITLE', 'name APP_EXE embedded',
        'emoji ☕', '\x00null', "'single'", 'A' * 300,
    ]
    for i, title in enumerate(titles):
        root = base / f'proj{i}'
        root.mkdir(parents=True, exist_ok=True)
        plan = {'content': {'title': title}}
        graceful(f'write_entry[{title!r:.24}]',
                 lambda root=root, plan=plan: package.write_entry(root, plan))
        entry = root / 'main.py'
        if entry.is_file():
            src = entry.read_text(encoding='utf-8')
            try:
                ast.parse(src)
                OK[0] += 1
            except SyntaxError as exc:
                BUGS.append(f'[write_entry_syntax[{title!r:.24}]] generated invalid Python: {exc}')


def pass_hostile_plans(base):
    root = base / 'planproj'
    root.mkdir(parents=True, exist_ok=True)
    bad_plans = [
        None, [], 'string', 42,
        {}, {'content': None}, {'content': []}, {'content': 'x'},
        {'content': {'title': None}}, {'content': {'title': 123}},
        {'content': {}},
    ]
    for i, plan in enumerate(bad_plans):
        r = root / f'p{i}'
        r.mkdir(exist_ok=True)
        graceful(f'write_entry_plan[{plan!r:.30}]',
                 lambda r=r, plan=plan: package.write_entry(r, plan))
    # package_project with no app.py must raise SafetyError, not crash
    for i, plan in enumerate(bad_plans):
        r = root / f'q{i}'
        r.mkdir(exist_ok=True)
        graceful(f'package_no_app[{plan!r:.30}]',
                 lambda r=r, plan=plan: package.package_project(r, r / 'dist', plan=plan))


def pass_convert():
    # The generated _convert must never raise on arbitrary argv strings.
    tree = ast.parse(package.ENTRY)
    conv_node = next(n for n in tree.body
                     if isinstance(n, ast.FunctionDef) and n.name == '_convert')
    ns = {}
    exec(compile(ast.Module(body=[conv_node], type_ignores=[]), 'entry', 'exec'), ns)  # noqa: S102
    conv = ns['_convert']
    for v in ['3', '3.5', 'x', '', '  ', '1e9', 'inf', 'nan', '0x10',
              '-0', '1_000', '٣', '½', 'True']:
        graceful(f'_convert[{v!r}]', lambda v=v: conv(v))


def pass_find_packager():
    graceful('find_packager_empty', lambda: package.find_packager_python([]))
    graceful('find_packager_bad', lambda: package.find_packager_python(['/nonesuch/python', '']))


def pass_self_check(base):
    for state in [base / 'missing_state', base / 'made_state', Path('/')]:
        if 'made' in state.name:
            state.mkdir(exist_ok=True)
        graceful(f'self_check[{state.name}]', lambda state=state: diagnostics.self_check(state))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        pass_exe_name()
        pass_write_entry(base)
        pass_hostile_plans(base)
        pass_convert()
        pass_find_packager()
        pass_self_check(base)
    print(f'round10: {OK[0]} checks ok, {len(BUGS)} bugs')
    for b in BUGS:
        print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
