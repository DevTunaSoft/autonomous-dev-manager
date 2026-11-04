"""Isolated, bounded regression runner; does not silently turn timeouts into passes."""
from __future__ import annotations
import argparse
import hashlib
import tempfile
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import platform
import shutil
import time


def _environment() -> dict:
    """Descriptive provenance recorded with a report (not part of the resume fingerprint)."""
    return {'python_version': platform.python_version(), 'python_executable': str(Path(sys.executable).resolve()),
            'platform': platform.platform(), 'machine': platform.machine()}


def prune_logs(log_parent: Path, keep: int, protect: set[Path] = frozenset()) -> list[str]:
    """Delete the oldest ``regression-run-*`` directories beyond ``keep``.

    Directories containing any protected log (those referenced by the current
    checkpoint, or the active run) are never deleted, so resume evidence and
    failure logs of the current checkpoint survive. Returns removed names.
    """
    if keep < 1:
        raise ValueError('keep must be >= 1')
    log_parent = Path(log_parent).resolve()
    protected_dirs = {Path(p).resolve().parent if Path(p).suffix else Path(p).resolve() for p in protect}
    runs = sorted((d for d in log_parent.glob('regression-run-*') if d.is_dir() and not d.is_symlink()),
                  key=lambda d: d.stat().st_mtime, reverse=True)
    removed = []
    for old in runs[keep:]:
        if old.resolve() in protected_dirs:
            continue
        shutil.rmtree(old, ignore_errors=True)
        removed.append(old.name)
    return removed


def _terminate_group(proc: subprocess.Popen) -> None:
    """Terminate the entire test process tree on timeout, not just its parent."""
    if os.name == 'nt':
        try:
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=4, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if proc.poll() is None:
        proc.kill()


def _save_report(path: Path, report: dict) -> None:
    """Atomically checkpoint partial results, including interrupted runs."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.regression-', suffix='.json', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _file_sha256(path: Path) -> str:
    """Hash arbitrarily large diagnostic logs without loading them into memory."""
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def run_suite(root: Path, *, timeout_per_module: float = 90, python: str = sys.executable,
              progress_path: Path | None = None, on_progress=None,
              selected_modules: set[str] | None = None, max_total_seconds: float | None = None,
              resume: bool = False, keep_runs: int | None = None) -> dict:
    root = Path(root).resolve()
    if not 1 <= timeout_per_module <= 3600:
        raise ValueError('timeout_per_module must be 1..3600 seconds')
    tests = sorted((root / 'tests').glob('test_*.py'))
    if selected_modules is not None:
        available = {p.name for p in tests}
        unknown = set(selected_modules) - available
        if unknown:
            raise ValueError('Unknown test modules: ' + ', '.join(sorted(unknown)))
        tests = [p for p in tests if p.name in selected_modules]
    if max_total_seconds is not None and max_total_seconds <= 0:
        raise ValueError('max_total_seconds must be positive')
    if not tests:
        raise ValueError('No test modules found')
    # Resume only against exactly the same Python source and tests. A source edit
    # invalidates all prior passes, preventing stale evidence from certifying a build.
    digest = hashlib.sha256()
    # A checkpoint from a different Python executable is not interchangeable.
    digest.update(str(Path(python).resolve()).encode('utf-8'))
    for source in sorted(root.rglob('*.py')):
        if any(part.startswith('.') or part == '__pycache__' for part in source.relative_to(root).parts):
            continue
        digest.update(str(source.relative_to(root)).encode())
        digest.update(hashlib.sha256(source.read_bytes()).digest())
    fingerprint = digest.hexdigest()
    report = {'kind': 'isolated_regression', 'fingerprint': fingerprint, 'modules': [],
              'passed': False, 'total_tests': 0, 'running': None,
              'environment': _environment()}
    completed = {}
    if resume:
        if progress_path is None:
            raise ValueError('resume requires progress_path')
        if Path(progress_path).exists():
            previous = json.loads(Path(progress_path).read_text(encoding='utf-8'))
            if previous.get('fingerprint') != fingerprint:
                raise ValueError('Source changed since checkpoint; cannot resume stale test evidence')
            # Checkpoints are only reusable when their original full test logs
            # still exist and match their recorded digests. Missing, changed or
            # legacy un-hashed evidence must be rerun, never silently trusted.
            for module in previous.get('modules', []):
                if module.get('status') != 'passed' or module.get('tests', 0) < 1:
                    continue
                log_name = module.get('log_path')
                expected = module.get('log_sha256')
                if not log_name or not expected:
                    continue
                log_file = Path(log_name)
                if not log_file.is_file():
                    continue
                if _file_sha256(log_file) != expected:
                    continue
                completed[module['module']] = module
    if progress_path is not None:
        _save_report(progress_path, report)
    # Each invocation owns a private log directory. Concurrent regression runs
    # must never overwrite one another's evidence or invalidate resume hashes.
    log_parent = (progress_path.parent if progress_path else root / '.adm-test-logs')
    log_parent.mkdir(parents=True, exist_ok=True)
    run_log_dir = Path(tempfile.mkdtemp(prefix='regression-run-', dir=log_parent))
    suite_started = time.monotonic()
    for path in tests:
        if path.name in completed:
            old = dict(completed[path.name])
            old['resumed'] = True
            report['modules'].append(old)
            report['total_tests'] += old['tests']
            if progress_path is not None:
                _save_report(progress_path, report)
            continue
        remaining = None if max_total_seconds is None else max_total_seconds - (time.monotonic() - suite_started)
        if remaining is not None and remaining <= 0:
            report['modules'].append({'module': path.name, 'status': 'not_run_budget',
                                      'exit_code': None, 'tests': 0, 'seconds': 0,
                                      'output_tail': 'Overall time budget exhausted'})
            if progress_path is not None:
                _save_report(progress_path, report)
            continue
        name = path.name
        start = time.monotonic()
        report['running'] = name
        if progress_path is not None:
            _save_report(progress_path, report)
        if on_progress is not None:
            on_progress(name, 'started')
        cmd = [python, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', name, '-v']
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        # Each module owns a dedicated process group so timed-out descendants
        # cannot keep stdout pipes open or outlive the regression runner.
        # Spool output to disk so evidence survives even if the test runner is
        # terminated externally. Pipes can otherwise obscure the last test.
        log_path = run_log_dir / (name + '.log')
        with log_path.open('wb') as log:
            with subprocess.Popen(cmd, cwd=root, env=env, stdout=log,
                                  stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                  start_new_session=(os.name != 'nt'),
                                  creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)) as proc:
                try:
                    proc.wait(timeout=min(timeout_per_module, remaining) if remaining is not None else timeout_per_module)
                    status = 'passed' if proc.returncode == 0 else 'failed'
                    exit_code = proc.returncode
                except subprocess.TimeoutExpired:
                    _terminate_group(proc)
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=2)
                    status, exit_code = 'timeout', None
        # Capture a bounded tail, preserving the full file for diagnosis.
        log_sha256 = _file_sha256(log_path)
        with log_path.open('rb') as log:
            log.seek(max(0, log_path.stat().st_size - 16000))
            output = log.read().decode('utf-8', 'replace')
        import re
        match = re.search(r'Ran (\d+) tests? in', output)
        count = int(match.group(1)) if match else 0
        # A module that imports successfully but discovers no tests is not evidence.
        if status == 'passed' and count == 0:
            # A successful interpreter exit without a unittest summary is not evidence.
            status = 'no_tests'
        elif status == 'failed' and count == 0 and match:
            status = 'no_tests'
        report['total_tests'] += count
        report['modules'].append({'module': name, 'status': status, 'exit_code': exit_code,
                                  'tests': count, 'seconds': round(time.monotonic()-start, 3),
                                  'output_tail': output[-3000:], 'log_path': str(log_path),
                                  'log_sha256': log_sha256})
        report['running'] = None
        if progress_path is not None:
            _save_report(progress_path, report)
        if on_progress is not None:
            on_progress(name, status)
    report['passed'] = all(m['status'] == 'passed' for m in report['modules'])
    if keep_runs is not None:
        protect = {run_log_dir} | {Path(m['log_path']) for m in report['modules'] if m.get('log_path')}
        report['pruned_runs'] = prune_logs(log_parent, keep_runs, protect)
    if progress_path is not None:
        _save_report(progress_path, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run regression tests with module isolation and timeouts')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--timeout', type=float, default=90)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--module', action='append', help='Run only this test module; repeatable')
    parser.add_argument('--max-total-seconds', type=float, help='Overall execution budget')
    parser.add_argument('--resume', action='store_true', help='Resume passing modules from matching source checkpoint')
    parser.add_argument('--keep-runs', type=int, help='Keep only the newest N log directories (never ones the checkpoint references)')
    args = parser.parse_args(argv)
    report = run_suite(args.root, timeout_per_module=args.timeout, progress_path=args.output,
                       on_progress=lambda name, state: print(f'{name}: {state}', flush=True),
                       selected_modules=set(args.module) if args.module else None,
                       max_total_seconds=args.max_total_seconds, resume=args.resume,
                       keep_runs=args.keep_runs)
    data = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding='utf-8')
    for m in report['modules']:
        print(f"{m['module']}: {m['status']} ({m['tests']} tests; {m['seconds']}s)", flush=True)
    print(f"OVERALL: {'PASS' if report['passed'] else 'FAIL'}; {report['total_tests']} completed tests", flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
