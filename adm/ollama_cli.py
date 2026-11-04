"""Run a local Ollama direct-repair trial on a trusted disposable project."""
import argparse
import json
from .ollama_direct import direct_repair


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--model', default='ollama/qwen2.5-coder:3b')
    parser.add_argument('--repairs', type=int, default=2)
    args = parser.parse_args()
    result = direct_repair(args.root, args.evidence, model=args.model, max_repairs=args.repairs)
    print(json.dumps({'status': result['status'], 'attempts': len(result['attempts']),
                      'live_model_verified': result['live_model_verified']}, indent=2))
    if result['status'] not in ('verified_direct_repair', 'baseline_passed'):
        raise SystemExit(1)

if __name__ == '__main__':
    main()
