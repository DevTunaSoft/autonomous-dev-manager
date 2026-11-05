"""Run a local direct-repair trial on a trusted disposable project."""
import argparse
import json
from .ollama_direct import direct_repair, request_patch
from .backends import make_generator


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--model', default='ollama/qwen2.5-coder:3b',
                        help='ollama/<name> or local/<name> (OpenAI-compatible server on this PC)')
    parser.add_argument('--endpoint', default='', help='needed for local/ models, e.g. http://127.0.0.1:1337')
    parser.add_argument('--repairs', type=int, default=2)
    parser.add_argument('--escalate-model', default='',
                        help='a larger model on this PC to switch to after --escalate-after failed tries')
    parser.add_argument('--escalate-endpoint', default='')
    parser.add_argument('--escalate-after', type=int, default=2)
    args = parser.parse_args()
    kwargs = {}
    if args.model.startswith('local/'):
        kwargs['generator'] = make_generator(args.model, endpoint=args.endpoint)
    if args.escalate_model:
        if args.escalate_model.startswith('remote/'):
            parser.error('Remote models need an approval step that this command does not provide')
        kwargs.update(escalation_model=args.escalate_model, escalate_after=args.escalate_after,
                      escalation_generator=make_generator(args.escalate_model, endpoint=args.escalate_endpoint))
    result = direct_repair(args.root, args.evidence, model=args.model, max_repairs=args.repairs, **kwargs)
    print(json.dumps({'status': result['status'], 'attempts': len(result['attempts']),
                      'live_model_verified': result['live_model_verified'],
                      'network_generator': result.get('network_generator', False),
                      'escalation_used': result['escalation']['used']}, indent=2))
    if result['status'] not in ('verified_direct_repair', 'baseline_passed'):
        raise SystemExit(1)

if __name__ == '__main__':
    main()
