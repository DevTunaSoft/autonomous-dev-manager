"""Opt-in real Ollama acceptance on a fresh, disposable fixture.

No fixture server, mocked model, remote API, or existing user project is accepted.
The generated code is executed locally WITHOUT an OS sandbox: use a disposable VM.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .agent import safe_local_model
from .engine import SafetyError, make_broken_demo
from .ollama_health import inspect_ollama
from .ollama_direct import direct_repair, request_patch


def run_live_acceptance(output_dir, *, model='ollama/qwen2.5-coder:3b', timeout=120,
                        health=inspect_ollama, repair=direct_repair):
    safe_local_model(model)
    output = Path(output_dir).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise SafetyError('Live acceptance requires an empty destination; existing files are never overwritten')
    # Validate the model before creating or executing a project.
    health_result = health()
    name = model.removeprefix('ollama/')
    if not health_result.get('reachable') or name not in health_result.get('installed_models', []):
        raise SafetyError('Requested model is not installed on the local Ollama server')
    output.mkdir(parents=True, exist_ok=True)
    root = make_broken_demo(output / 'demo-project')
    evidence = output / 'evidence'
    report = repair(root, evidence, model=model, timeout=timeout, max_repairs=2)
    # Explicitly distinguish real inference from a mocked adapter, and require tests.
    attempts = report.get('attempts', [])
    verified = (repair is direct_repair and report.get('network_generator') is True
                and report.get('status') == 'verified_direct_repair'
                and report.get('baseline', {}).get('exit_code') != 0
                and any(a.get('passed') and a.get('test', {}).get('exit_code') == 0 for a in attempts)
                and not (evidence / 'repair-journal.json').exists())
    summary = {'passed': bool(verified), 'real_model_verified': bool(verified),
               'model': model, 'model_installed': True,
               'repair_status': report.get('status'),
               'warning': 'Generated code was executed without an OS sandbox; disposable VM only',
               'report_path': str(evidence / 'ollama-direct-report.json')}
    (output / 'live-acceptance-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description='Opt-in real Ollama test; run only inside a disposable VM')
    parser.add_argument('--output', required=True)
    parser.add_argument('--model', default='ollama/qwen2.5-coder:3b')
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--acknowledge-unsandboxed-code', action='store_true')
    args = parser.parse_args(argv)
    if not args.acknowledge_unsandboxed_code:
        parser.error('Requires --acknowledge-unsandboxed-code; use a disposable VM')
    try:
        result = run_live_acceptance(args.output, model=args.model, timeout=args.timeout)
    except (SafetyError, OSError) as exc:
        print(json.dumps({'passed': False, 'real_model_verified': False, 'error': str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
