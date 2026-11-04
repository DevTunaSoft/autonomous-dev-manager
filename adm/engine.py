"""ADM-002: bounded, evidence-backed autonomous repair proof (standard library)."""
from __future__ import annotations
import hashlib
import json
import os
import signal
from pathlib import Path
import shutil
import subprocess
import sys
import time

from .core import Supervisor, resources, mode


MAX_CAPTURE_BYTES = 64 * 1024 * 1024   # a runaway test must not fill the disk or RAM


class SafetyError(ValueError):
    pass


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def run_checked(argv, cwd, root, timeout=90, output_limit=30000):
    """Run a fixed executable, never a shell; ensure cwd is inside the project."""
    cwd, root = Path(cwd).resolve(), Path(root).resolve()
    if not inside(cwd, root) or not cwd.is_dir():
        raise SafetyError('Working directory escapes approved project')
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
        raise SafetyError('Command must be a nonempty argument list')
    if timeout <= 0 or timeout > 600:
        raise SafetyError('Timeout outside allowed range')
    # This is a trusted-runner proof, not a hostile-code sandbox.
    started = time.time()
    proc = None
    import tempfile
    try:
        # Own a separate process group so a timeout stops child processes too.
        # This is process lifecycle management, NOT a security sandbox.
        options = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
                   if os.name == 'nt' else {'start_new_session': True})
        # Output goes to a temp file (stdout+stderr interleaved), never an unbounded pipe.
        with tempfile.TemporaryFile() as sink:
            proc = subprocess.Popen(argv, cwd=cwd, shell=False, stdin=subprocess.DEVNULL,
                                    stdout=sink, stderr=subprocess.STDOUT, **options)
            reason = None
            deadline = time.monotonic() + timeout
            while proc.poll() is None:
                if time.monotonic() >= deadline:
                    reason = f'Timed out after {timeout}s; process tree termination requested.\n'
                    break
                if os.fstat(sink.fileno()).st_size > MAX_CAPTURE_BYTES:
                    reason = 'Output exceeded 64 MiB; process tree termination requested.\n'
                    break
                time.sleep(0.05)
            if reason:
                if os.name == 'nt':
                    # Windows taskkill /T terminates the entire descendant tree.
                    # Never use shell=True or interpolate command text.
                    try:
                        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                                       capture_output=True, timeout=10, check=False)
                    except (OSError, subprocess.TimeoutExpired):
                        proc.kill()
                else:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
            size = os.fstat(sink.fileno()).st_size
            sink.seek(max(0, size - output_limit))
            tail = sink.read().decode('utf-8', 'replace')
            code = 124 if reason else proc.returncode
            # Keep the explanation even when the tail fills the whole budget.
            budget = max(0, output_limit - len(reason or ''))
            output = (reason or '') + (tail[-budget:] if budget else '')
    except OSError as ex:
        code, output = 127, f'Launch failed: {ex}'
    return {'argv': argv, 'exit_code': code, 'output': output if len(output) <= output_limit else output[-output_limit:],
            'elapsed_seconds': round(time.time() - started, 3)}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_broken_demo(root):
    """Create a controlled example with a real failing test and deterministic fix."""
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise SafetyError('Demo destination must be empty; will not overwrite user files')
    (root / 'calculator.py').write_text('def add(a, b):\n    return a - b\n', encoding='utf-8')
    (root / 'test_calculator.py').write_text('import unittest\nfrom calculator import add\n\nclass TestCalculator(unittest.TestCase):\n    def test_positive(self):\n        self.assertEqual(add(2, 3), 5)\n    def test_negative(self):\n        self.assertEqual(add(-4, 2), -2)\n\nif __name__ == "__main__":\n    unittest.main()\n', encoding='utf-8')
    (root / 'requirements.json').write_text(json.dumps({
        'requirements': [{'id': 'DEMO-001', 'description': 'add(a,b) returns mathematical sum',
                          'tests': ['test_calculator.TestCalculator.test_positive',
                                    'test_calculator.TestCalculator.test_negative']}]
    }, indent=2), encoding='utf-8')
    return root


def demo_repair(root):
    """Narrow verified repair recipe; never infer arbitrary code fixes from text."""
    path = Path(root) / 'calculator.py'
    original = 'def add(a, b):\n    return a - b\n'
    if not path.is_file() or path.read_text(encoding='utf-8') != original:
        return False
    path.write_text('def add(a, b):\n    return a + b\n', encoding='utf-8')
    return True


def proof(root, evidence_dir, repair=demo_repair, interrupt_after_failure=False):
    """Run actual tests, repair once, re-run; emit evidence. Does not assert general AI autonomy."""
    root, evidence_dir = Path(root).resolve(), Path(evidence_dir).resolve()
    if not root.is_dir():
        raise SafetyError('Project directory missing')
    if inside(evidence_dir, root):
        raise SafetyError('Evidence directory must be outside project workspace')
    evidence_dir.mkdir(parents=True, exist_ok=True)
    db = Supervisor(evidence_dir / 'supervisor')
    report_path = evidence_dir / 'proof-report.json'
    from .pyruntime import project_python
    test_argv = [project_python(), '-B', '-m', 'unittest', 'discover', '-s', '.', '-p', 'test_*.py', '-v']
    try:
        report = {'schema_version': 1, 'project': str(root), 'environment': resources(),
                  'resource_mode': mode(resources()), 'tests': [], 'repair': None,
                  'status': 'not_verified', 'note': 'Deterministic demo repair, not an AI coding agent'}
        if report_path.exists():
            prior = json.loads(report_path.read_text(encoding='utf-8'))
            if prior.get('status') == 'interrupted_after_failure':
                report = prior
        if not report['tests']:
            first = run_checked(test_argv, root, root)
            report['tests'].append({'phase': 'baseline', **first})
            if first['exit_code'] == 0:
                report['status'] = 'baseline_passed'
                report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
                return report
            if interrupt_after_failure:
                report['status'] = 'interrupted_after_failure'
                report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
                return report
        if report['repair'] is None:
            before = sha256(root / 'calculator.py') if (root / 'calculator.py').exists() else None
            repaired = repair(root)
            after = sha256(root / 'calculator.py') if (root / 'calculator.py').exists() else None
            report['repair'] = {'applied': bool(repaired), 'before_sha256': before, 'after_sha256': after}
            report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        final = run_checked(test_argv, root, root)
        report['tests'].append({'phase': 'post_repair', **final})
        # Gate success on a real initially failing test, an actual changed file, and final passing tests.
        report['status'] = ('verified_demo' if report['tests'][0]['exit_code'] != 0
                            and report['repair']['applied']
                            and report['repair']['before_sha256'] != report['repair']['after_sha256']
                            and final['exit_code'] == 0 else 'failed')
        report['source_sha256'] = sha256(root / 'calculator.py') if (root / 'calculator.py').exists() else None
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        return report
    finally:
        db.close()
