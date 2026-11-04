"""Read-only CLI for reconciling a queued AI repair with its evidence."""
import argparse
import json
from .queued_ai import inspect_repair


def main(argv=None):
    parser = argparse.ArgumentParser(description='Inspect an AI repair without changing it')
    parser.add_argument('--state', required=True)
    parser.add_argument('--job', type=int, required=True)
    args = parser.parse_args(argv)
    result = inspect_repair(args.state, args.job)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result['verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
