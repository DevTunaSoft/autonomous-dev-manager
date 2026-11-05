"""ADM-006: durable, fail-closed supervised local agent proof.

Runs the existing agent CLI in a supervised worker process. This is not a
sandbox, an unattended service, or proof of real AI until a live run succeeds.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import time
from .agent import safe_local_model, validate_project, protected_hashes
from .engine import SafetyError, inside
from .worker import WorkerSupervisor


def start_pipeline(state_dir, project, evidence, *, model='ollama/qwen2.5-coder:3b',
                   max_repairs=2, timeout=180):
    """Create one durable supervised agent job, without starting it."""
    model = safe_local_model(model)
    state_dir, project, evidence = (Path(p).resolve() for p in (state_dir, project, evidence))
    if not 1 <= max_repairs <= 5 or not 10 <= timeout <= 3600:
        raise SafetyError('Invalid repair or timeout limits')
    validate_project(project, evidence)
    if any(inside(a, b) or inside(b, a) for a, b in
           ((state_dir, project), (state_dir, evidence))):
        raise SafetyError('State, project and evidence directories must be separate')
    state_dir.mkdir(parents=True, exist_ok=True)
    spec = state_dir / 'pipeline.json'
    proposed = {'schema': 1, 'project': str(project), 'evidence': str(evidence),
                'model': model, 'repairs': max_repairs, 'timeout': timeout,
                'protected': protected_hashes(project)}
    sup = WorkerSupervisor(state_dir / 'workers')
    try:
        if spec.exists():
            existing = json.loads(spec.read_text(encoding='utf-8'))
            if {k: existing.get(k) for k in proposed} != proposed:
                raise SafetyError('Existing pipeline specification differs; refusing to overwrite')
            return existing['job_id'] if 'job_id' in existing else _existing_job(sup)
        # Worker process must be importable from a checkout without pip install.
        entry = Path(__file__).resolve().parents[1] / 'adm' / 'agent_cli.py'
        # `-m adm.agent_cli` works when running from the checkout's root.
        from .pyruntime import self_command
        command = self_command('adm.agent_cli', ['repair', '--root', str(project), '--evidence', str(evidence),
                                                 '--model', model, '--repairs', str(max_repairs)])
        jid = sup.add('supervised-local-ai-repair', command, entry.parent.parent,
                      max_attempts=1)
        # Job is intentionally not retried: unknown external agent edits cannot
        # safely be replayed after an interrupted attempt.
        proposed['job_id'] = jid
        from .agent import atomic_json
        atomic_json(spec, proposed)
        return jid
    finally:
        sup.close()


def _existing_job(sup):
    jobs = sup.status()
    if len(jobs) != 1:
        raise SafetyError('Ambiguous worker state')
    return jobs[0]['id']


def run_pipeline(state_dir, *, timeout=180):
    """Run one queued worker and reconcile its real evidence. Never infer success
    from an agent's prose or from the worker's exit code alone."""
    state_dir = Path(state_dir).resolve()
    spec_path = state_dir / 'pipeline.json'
    if not spec_path.is_file():
        raise SafetyError('No pipeline to run; start one first')
    try:
        spec = json.loads(spec_path.read_text(encoding='utf-8'))
    except (OSError, ValueError, RecursionError) as exc:
        raise SafetyError('Pipeline spec is unreadable') from exc
    if not isinstance(spec, dict) or 'job_id' not in spec:
        raise SafetyError('Pipeline spec is malformed')
    sup = WorkerSupervisor(state_dir / 'workers')
    try:
        recovered = sup.recover(stale_after=30)
        jobs = sup.status()
        if len(jobs) != 1 or jobs[0]['id'] != spec['job_id']:
            raise SafetyError('Unexpected worker queue; cannot determine pipeline ownership')
        if jobs[0]['state'] == 'pending':
            sup.run_once(timeout=timeout, heartbeat_interval=0.2)
        job = sup.status()[0]
    finally:
        sup.close()
    evidence = Path(spec['evidence']) / 'agent-proof-report.json'
    report = None
    if evidence.exists():
        try:
            report = json.loads(evidence.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass
    protected = protected_hashes(Path(spec['project']))
    verified = (job['state'] == 'passed' and report is not None
                and report.get('status') == 'verified_agent_repair'
                and report.get('project') == spec['project']
                and report.get('model') == spec['model']
                and report.get('protected_before') == spec['protected']
                and protected == spec['protected']
                and any(a.get('test', {}).get('exit_code') == 0
                        and a.get('protected_unchanged') and a.get('source_changed')
                        for a in report.get('attempts', [])))
    return {'status': 'verified' if verified else 'not_verified',
            'worker': job, 'agent_report_status': report.get('status') if report else None,
            'recovered': recovered, 'evidence': str(evidence)}
