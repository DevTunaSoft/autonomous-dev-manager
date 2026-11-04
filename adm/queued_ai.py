"""Queue a bounded local-Ollama repair for the persistent ADM supervisor.

Trusted disposable projects only. This is NOT a sandbox. No paid API calls.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import uuid
from .agent import safe_local_model, validate_project
from .model_selection import select_installed_model
from .ollama_health import inspect_ollama
from .engine import SafetyError
from .worker import WorkerSupervisor



def physical_ram_gib():
    """Physical RAM capacity, not available RAM. Fail closed if unknown."""
    import os
    import sys
    if sys.platform == 'win32':
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                       ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                       ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                       ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                       ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise SafetyError('Unable to determine Windows physical RAM')
        return status.ullTotalPhys / (1024 ** 3)
    try:
        return os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE') / (1024 ** 3)
    except (ValueError, OSError, AttributeError) as exc:
        raise SafetyError('Unable to determine physical RAM') from exc

def enqueue_repair(state, root, evidence_base, *, model='ollama/qwen2.5-coder:3b', repairs=2,
                   ram_gib=None, installed_models=None):
    # Explicit model remains backward compatible. Automatic mode never guesses
    # installed models or downloads them. Inventory and RAM must be grounded.
    selection = None
    if model == 'auto':
        if ram_gib is None:
            ram_gib = physical_ram_gib()
        if installed_models is None:
            installed_models = inspect_ollama()['installed_models']
        selection = select_installed_model(installed_models, ram_gib=ram_gib)
        model = selection['model']
    safe_local_model(model)
    if not isinstance(repairs, int) or not 1 <= repairs <= 5:
        raise SafetyError('Repairs must be 1..5')
    state, root, evidence_base = (Path(p).resolve() for p in (state, root, evidence_base))
    if root == state or root == evidence_base or root in state.parents or state in root.parents:
        raise SafetyError('Project and supervisor state must be separate')
    if evidence_base == state or evidence_base in state.parents or state in evidence_base.parents:
        raise SafetyError('Evidence and supervisor state must be separate')
    validate_project(root, evidence_base)
    # Each queued job owns a unique evidence directory; worker retries disabled to
    # avoid replaying partially completed model edits after a crash.
    evidence = evidence_base / ('job-' + uuid.uuid4().hex)
    package_root = str(Path(__file__).resolve().parent.parent)
    launcher = ('import sys; sys.path.insert(0, ' + repr(package_root) + '); '
                'from adm.ollama_cli import main; main()')
    argv = [sys.executable, '-B', '-c', launcher, '--root', str(root),
            '--evidence', str(evidence), '--model', model, '--repairs', str(repairs)]
    worker = WorkerSupervisor(state)
    try:
        job_id = worker.add('local-ai-repair', argv, root, max_attempts=1)
        worker.event(job_id, 'ai_repair_queued', evidence=str(evidence), model=model)
    finally:
        worker.close()
    return {'job_id': job_id, 'evidence': str(evidence), 'model': model,
            'selection': selection, 'inference_verified': False}


def main(argv=None):
    p = argparse.ArgumentParser(description='Queue trusted local Ollama repair for ADM daemon')
    p.add_argument('--state', required=True)
    p.add_argument('--root', required=True)
    p.add_argument('--evidence', required=True)
    p.add_argument('--model', default='auto', help='auto selects an installed local model; explicit ollama/... is also supported')
    p.add_argument('--ram-gib', type=float, help='Override physical RAM in GiB for testing')
    p.add_argument('--repairs', type=int, default=2)
    args = p.parse_args(argv)
    print(json.dumps(enqueue_repair(args.state, args.root, args.evidence,
                                    model=args.model, repairs=args.repairs, ram_gib=args.ram_gib), indent=2))

if __name__ == '__main__':
    main()


def inspect_repair(state, job_id):
    """Read-only reconciliation of durable worker state and AI evidence.

    A worker exit code alone is insufficient to prove a successful AI repair.
    This routine never executes, resumes, or modifies an interrupted job.
    """
    if not isinstance(job_id, int) or isinstance(job_id, bool) or job_id < 1:
        raise SafetyError('Invalid job ID')
    worker = WorkerSupervisor(Path(state).resolve())
    try:
        row = worker.db.execute(
            'SELECT label,argv,state,exit_code,error FROM jobs WHERE id=?', (job_id,)).fetchone()
    finally:
        worker.close()
    if not row or row[0] != 'local-ai-repair':
        raise SafetyError('AI repair job not found')
    try:
        argv = json.loads(row[1])
        index = argv.index('--evidence')
        evidence = Path(argv[index + 1]).resolve()
    except (ValueError, IndexError, TypeError) as exc:
        raise SafetyError('Invalid stored repair command') from exc
    report_file = evidence / 'ollama-direct-report.json'
    journal = evidence / 'repair-journal.json'
    report = None
    if report_file.is_file():
        try:
            report = json.loads(report_file.read_text(encoding='utf-8'))
            if not isinstance(report, dict):
                raise ValueError('report must be an object')
        except (ValueError, OSError) as exc:
            return {'job_id': job_id, 'worker_state': row[2], 'status': 'invalid_evidence',
                    'verified': False, 'reason': str(exc), 'evidence': str(evidence)}
    state_value = row[2]
    verified = (state_value == 'passed' and row[3] == 0 and not journal.exists()
                and report is not None and report.get('status') in
                ('verified_direct_repair', 'baseline_passed'))
    if journal.exists():
        status = 'recovery_required'
    elif verified:
        status = 'verified_by_recorded_tests'
    elif state_value in ('pending', 'starting', 'running'):
        status = 'in_progress'
    elif state_value == 'blocked':
        status = 'blocked'
    elif state_value == 'passed':
        status = 'evidence_mismatch'
    else:
        status = 'failed_or_incomplete'
    return {'job_id': job_id, 'worker_state': state_value, 'status': status,
            'verified': verified, 'evidence': str(evidence),
            'report_status': report.get('status') if report else None,
            'live_model_verified': bool(report.get('live_model_verified')) if report else False,
            'reason': row[4]}
