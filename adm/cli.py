"""Human-friendly ADM-002 proof command."""
import argparse
import json
from pathlib import Path
from .engine import make_broken_demo, proof


def main():
    p = argparse.ArgumentParser(description='ADM-002 real test and deterministic repair proof')
    p.add_argument('action', choices=['demo', 'resume'])
    p.add_argument('--root', default='adm-demo-project')
    p.add_argument('--evidence', default='adm-demo-evidence')
    p.add_argument('--interrupt', action='store_true', help='simulate interruption after failing baseline')
    a = p.parse_args()
    if a.action == 'demo':
        make_broken_demo(a.root)
    result = proof(a.root, a.evidence, interrupt_after_failure=a.interrupt)
    print(json.dumps({'status': result['status'], 'report': str(Path(a.evidence) / 'proof-report.json'),
                      'tests': [(t['phase'], t['exit_code']) for t in result['tests']]}, indent=2))
    if result['status'] not in ('verified_demo', 'baseline_passed', 'interrupted_after_failure'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
