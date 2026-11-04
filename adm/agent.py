"""ADM-003: guarded OpenCode/Ollama adapter and evidence-backed repair trial.

This is NOT a security sandbox. Only use trusted disposable projects until an OS
isolation mechanism exists. The verification step checks protected source files,
but cannot prevent a coding agent from accessing files outside the project.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from typing import Sequence

from .core import resources, mode
from .engine import SafetyError, inside, run_checked
from .recovery import save_snapshot, restore_snapshot, inventory


def safe_local_model(model: str) -> str:
    """Fail closed: only explicit Ollama model identifiers are accepted."""
    if not isinstance(model, str) or not model.startswith('ollama/'):
        raise SafetyError('Only explicitly selected local Ollama models are allowed')
    rest = model[len('ollama/'):]
    if not rest or len(rest) > 120 or not all(c.isalnum() or c in '._:/+-' for c in rest):
        raise SafetyError('Invalid local model identifier')
    return model


def validate_project(root: Path, evidence: Path) -> None:
    if not root.is_dir() or inside(evidence, root) or inside(root, evidence):
        raise SafetyError('Project must exist and evidence must be in a separate directory')
    # Reject symlinks, which can make protected-file checks misleading.
    for path in root.rglob('*'):
        if path.is_symlink():
            raise SafetyError('Project symlinks are not supported by this proof')
    if not (root / 'requirements.json').is_file():
        raise SafetyError('Project must have requirements.json')
    if not any(root.glob('test_*.py')):
        raise SafetyError('Project must have top-level test_*.py files')
    if not any(root.glob('*.py')):
        raise SafetyError('Project must contain Python source files')


def protected_hashes(root: Path) -> dict[str, str]:
    """Protected tests and requirements must not be changed by the agent."""
    paths = sorted(set(root.rglob('test_*.py')) | {root / 'requirements.json'})
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths if p.is_file()}


def source_hashes(root: Path) -> dict[str, str]:
    paths = sorted(p for p in root.rglob('*.py') if not p.name.startswith('test_')
                   and '__pycache__' not in p.parts)
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.adm-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def test_command() -> list[str]:
    from .pyruntime import project_python
    return [project_python(), '-B', '-m', 'unittest', 'discover', '-s', '.', '-p', 'test_*.py', '-v']


def make_prompt(requirements: str, failing_output: str, attempt: int) -> str:
    return ("You are repairing a small, trusted, disposable Python project. "
            "Implement the existing requirements and repair the failure below. "
            "Change application source files only. Do not modify requirements.json, "
            "test files, testing configuration, or files outside this workspace. "
            "Do not weaken assertions or skip tests. Prefer the smallest correct fix. "
            "Do not use external cloud providers. If you cannot repair the program, say so.\n\n"
            f"Attempt: {attempt}\nRequirements:\n{requirements[:12000]}\n\n"
            f"Actual failing test output:\n{failing_output[-12000:]}")


def run_agent(root: Path, model: str, prompt: str, executable: Sequence[str], timeout: int) -> dict:
    if not executable or any(not isinstance(s, str) or not s for s in executable):
        raise SafetyError('Invalid agent executable')
    # OpenCode's documented noninteractive run path. No --auto is used.
    argv = [*executable, 'run', '--model', model, '--agent', 'build', prompt]
    return run_checked(argv, root, root, timeout=timeout)


def agent_repair_proof(root, evidence_dir, *, model='ollama/qwen2.5-coder:3b',
                       agent_executable=None, max_repairs=2, timeout=90,
                       interrupt_after_baseline=False):
    """Integrate an external agent and verify real results; no assumed AI success.

    `agent_executable` injection is for deterministic test fakes. The public CLI
    never exposes that override, preventing accidental use of untrusted wrappers.
    """
    model = safe_local_model(model)
    if not isinstance(max_repairs, int) or not 1 <= max_repairs <= 5:
        raise SafetyError('max_repairs must be between 1 and 5')
    root, evidence_dir = Path(root).resolve(), Path(evidence_dir).resolve()
    validate_project(root, evidence_dir)
    agent = list(agent_executable) if agent_executable is not None else ['opencode']
    if agent_executable is None and not shutil.which('opencode'):
        raise SafetyError('OpenCode is not installed or not on PATH')
    report_path = evidence_dir / 'agent-proof-report.json'
    # Loading checkpoint only for same project/model; never reuse a verified result blindly.
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding='utf-8'))
        if report.get('project') != str(root) or report.get('model') != model:
            raise SafetyError('Existing report belongs to another project or model')
        if report.get('status') == 'verified_agent_repair':
            raise SafetyError('Already verified; use a new evidence directory for a new trial')
        if report.get('status') in ('agent_in_flight', 'verifying'):
            # Recover only from a verified pre-attempt snapshot. This assumes the
            # previously launched worker is no longer running; no OS sandbox yet.
            checkpoint = report.get('active_checkpoint')
            if not checkpoint:
                raise SafetyError('Interrupted attempt lacks recovery checkpoint')
            restore_snapshot(root, evidence_dir / 'snapshots' / str(checkpoint['number']),
                             checkpoint['hashes'])
            report['status'] = 'restored_after_interruption'
            report['recoveries'] = report.get('recoveries', 0) + 1
            report['active_checkpoint'] = None
            atomic_json(report_path, report)
        if protected_hashes(root) != report.get('protected_before'):
            raise SafetyError('Protected tests or requirements changed since checkpoint')
    else:
        report = {'schema_version': 1, 'project': str(root), 'model': model,
                  'environment': resources(), 'resource_mode': mode(resources()),
                  'status': 'not_verified', 'baseline': None, 'attempts': [],
                  'protected_before': protected_hashes(root),
                  'source_before': source_hashes(root),
                  'note': 'Test-fake runs do not prove live AI operation; not OS-sandboxed'}
    if report['baseline'] is None:
        baseline = run_checked(test_command(), root, root, timeout=timeout)
        report['baseline'] = baseline
        report['status'] = 'baseline_failed' if baseline['exit_code'] else 'baseline_passed'
        atomic_json(report_path, report)
        if baseline['exit_code'] == 0 or interrupt_after_baseline:
            return report
    failure_text = (report['attempts'][-1]['test']['output'] if report['attempts']
                    else report['baseline']['output'])
    requirements = (root / 'requirements.json').read_text(encoding='utf-8')
    for idx in range(len(report['attempts']), max_repairs):
        # Fail closed if there is unexplained workspace drift between attempts.
        # Each attempt has its own bounded, independently verified snapshot.
        snapshot_dir = evidence_dir / 'snapshots' / str(idx + 1)
        if snapshot_dir.exists():
            before = inventory(snapshot_dir)
            if inventory(root) != before:
                raise SafetyError('Existing retry snapshot differs from workspace')
        else:
            before = save_snapshot(root, snapshot_dir)
        report['active_checkpoint'] = {'number': idx + 1, 'hashes': before}
        # Record an in-flight attempt before letting agent change files.
        # On unexpected interruption, stop conservatively rather than blindly re-run.
        report['status'] = 'agent_in_flight'
        atomic_json(report_path, report)
        response = run_agent(root, model, make_prompt(requirements, failure_text, idx + 1), agent, timeout)
        # Save immediately; a crash after editing cannot be mistaken for clean baseline.
        report['status'] = 'verifying'
        atomic_json(report_path, report)
        current_protected = protected_hashes(root)
        unmodified = current_protected == report['protected_before']
        current_source = source_hashes(root)
        changed = current_source != report['source_before']
        # Always run the independent test suite even if the agent itself returned error.
        test_result = run_checked(test_command(), root, root, timeout=timeout)
        entry = {'number': idx + 1, 'agent': response, 'test': test_result,
                 'protected_unchanged': unmodified, 'source_changed': changed,
                 'source_sha256': current_source}
        report['attempts'].append(entry)
        report['active_checkpoint'] = None
        report['status'] = ('verified_agent_repair' if response['exit_code'] == 0
                            and test_result['exit_code'] == 0 and unmodified and changed
                            and report['baseline']['exit_code'] != 0 else 'repair_failed')
        atomic_json(report_path, report)
        if not unmodified:
            report['status'] = 'blocked_protected_files_modified'
            atomic_json(report_path, report)
            break
        if report['status'] == 'verified_agent_repair':
            break
        failure_text = test_result['output'] if test_result['exit_code'] else response['output']
    return report
