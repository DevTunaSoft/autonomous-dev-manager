"""Adversarial harness, round 28: sandbox command-builders — cmdline_for
(argv + stdout_path quoting safety) and refuse_hardened_location (bypass
attempts via extended-length prefixes, slashes, case, UNC, drive roots).
Pure string logic; runs on any OS."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.sandbox import cmdline_for, refuse_hardened_location, SandboxError, HARDEN_DIRS

BUGS = []
OK = [0]


def graceful(label, fn):
    try:
        fn()
        BUGS.append(f'[{label}] did NOT raise (accepted hostile input)')
    except SandboxError:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] raised {type(exc).__name__} (want SandboxError): {str(exc)[:120]}')


def must_raise_refuse(label, project):
    try:
        refuse_hardened_location(project)
        BUGS.append(f'[{label}] hardened/invalid location ACCEPTED: {project!r}')
    except SandboxError:
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] raised {type(exc).__name__} (want SandboxError): {str(exc)[:120]}')


def must_pass_refuse(label, project):
    try:
        refuse_hardened_location(project)
        OK[0] += 1
    except BaseException as exc:          # noqa: BLE001
        BUGS.append(f'[{label}] safe location REJECTED/raised {type(exc).__name__}: {project!r}')


def pass_cmdline_argv():
    bad = [[], [''], ['ok', ''], ['a\\'], ['a&b'], ['a|b'], ['a>b'], ['a<b'], ['a^b'],
           ['a"b'], ['a%b'], ['a\x00b'], ['a\rb'], ['a\nb'], ['ok', None], [123]]
    for i, argv in enumerate(bad):
        graceful(f'cmdline_argv[{i}]', lambda argv=argv: cmdline_for(argv, r'C:\ev\out.log'))
    # a valid argv produces a quoted command line
    cl = cmdline_for(['python', '-m', 'unittest'], r'C:\ev\out.log')
    OK[0] += 1 if cl.startswith('cmd.exe /c') and '"python"' in cl else BUGS.append(f'[cmdline_valid] {cl!r}')


def pass_cmdline_stdout():
    # The stdout path is interpolated into the command line; a quote or shell
    # metacharacter in it must not be able to break out of the quoting.
    for bad_out in [r'C:\ev\a"b.log', 'C:\\ev\\a&b.log', 'C:\\ev\\a\x00.log',
                    'C:\\ev\\a>b.log', 'C:\\ev\\a|b.log', 'C:\\ev\\a\n.log']:
        graceful(f'cmdline_stdout[{bad_out[-8:]!r}]', lambda bad_out=bad_out: cmdline_for(['python'], bad_out))


def pass_refuse_hardened():
    # every hardened dir, in several evasion forms, must be refused
    for d in HARDEN_DIRS:
        must_raise_refuse(f'exact[{d}]', d)
        must_raise_refuse(f'child[{d}]', d + r'\proj')
        must_raise_refuse(f'upper[{d}]', d.upper())
        must_raise_refuse(f'fwdslash[{d}]', d.replace('\\', '/') + '/proj')
        must_raise_refuse(f'trailing[{d}]', d + '\\')
        must_raise_refuse(f'extlen[{d}]', '\\\\?\\' + d + r'\proj')
    # drive roots refused
    for root in ['C:\\', 'C:', 'D:\\', '\\\\?\\C:\\']:
        must_raise_refuse(f'driveroot[{root}]', root)
    # genuinely safe project locations pass
    for safe in [r'C:\Users\alice\adm-projects\myapp', r'D:\work\thing',
                 r'C:\ProgramDataX\app',                       # not under ProgramData
                 r'C:\Users\PublicRecords\x']:                 # not under \Users\Public
        must_pass_refuse(f'safe[{safe}]', safe)


def main():
    pass_cmdline_argv()
    pass_cmdline_stdout()
    pass_refuse_hardened()
    print(f'round28: {OK[0]} checks ok, {len(BUGS)} bugs')
    for b in BUGS:
        print('  BUG', b)
    return 1 if BUGS else 0


if __name__ == '__main__':
    raise SystemExit(main())
