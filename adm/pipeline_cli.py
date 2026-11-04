"""Supervised local AI proof: no paid API, no automatic execution of unknown projects."""
import argparse
import json
from .pipeline import start_pipeline, run_pipeline


def main():
    p = argparse.ArgumentParser(description='ADM-006 supervised local AI proof')
    p.add_argument('action', choices=('prepare', 'run'))
    p.add_argument('--state', required=True)
    p.add_argument('--project')
    p.add_argument('--evidence')
    p.add_argument('--model', default='ollama/qwen2.5-coder:3b')
    p.add_argument('--timeout', type=int, default=180)
    args = p.parse_args()
    if args.action == 'prepare':
        if not args.project or not args.evidence:
            p.error('prepare requires --project and --evidence')
        print(json.dumps({'job_id': start_pipeline(args.state, args.project, args.evidence,
                                                   model=args.model, timeout=args.timeout)}))
    else:
        result = run_pipeline(args.state, timeout=args.timeout)
        print(json.dumps(result, indent=2))
        if result['status'] != 'verified':
            raise SystemExit(1)

if __name__ == '__main__':
    main()
