"""ADM-003 real local OpenCode agent trial CLI."""
import argparse
import json
from pathlib import Path
from .agent import agent_repair_proof
from .preflight import local_preflight
from .engine import SafetyError, make_broken_demo


def main():
    parser = argparse.ArgumentParser(description='ADM-003 trusted local agent repair proof')
    parser.add_argument('action', choices=('create-demo', 'repair', 'preflight'))
    parser.add_argument('--root', default='adm-agent-project')
    parser.add_argument('--evidence', default='adm-agent-evidence')
    parser.add_argument('--model', default='ollama/qwen2.5-coder:3b')
    parser.add_argument('--repairs', type=int, default=2)
    args = parser.parse_args()
    try:
        if args.action == 'preflight':
            result = local_preflight(args.model)
            print(json.dumps(result, indent=2))
            if not result['ready']:
                raise SystemExit(1)
            return
        if args.action == 'create-demo':
            print(f'Created controlled broken demo at {make_broken_demo(args.root)}')
            return
        result = agent_repair_proof(args.root, args.evidence, model=args.model,
                                    max_repairs=args.repairs)
        print(json.dumps({'status': result['status'],
                          'evidence': str(Path(args.evidence) / 'agent-proof-report.json'),
                          'attempts': len(result['attempts'])}, indent=2))
        if result['status'] not in ('verified_agent_repair', 'baseline_passed'):
            raise SystemExit(1)
    except SafetyError as error:
        parser.exit(2, f'Unable to run trial: {error}\n')


if __name__ == '__main__':
    main()
