"""Read-only setup plan by default; --apply is an explicit opt-in."""
import argparse
import json
from .setup import build_plan, execute_step


def main():
    parser = argparse.ArgumentParser(description='ADM local setup planning (safe preview by default)')
    parser.add_argument('--apply', action='store_true', help='Run allowlisted setup actions')
    parser.add_argument('--approve-downloads', action='store_true', help='Explicitly approve downloads/installations')
    args = parser.parse_args()
    plan = build_plan()
    print(json.dumps(plan, indent=2))
    if not args.apply:
        return 0
    if not args.approve_downloads:
        parser.error('--apply requires --approve-downloads')
    results = []
    for step in plan['steps']:
        result = execute_step(step, approved=True)
        results.append(result)
        print(json.dumps(result, indent=2))
        if result['status'] != 'completed':
            break
    # Even successful installs cannot certify the system while blockers remain.
    return 1 if plan['blockers'] or any(x['status'] != 'completed' for x in results) else 0


if __name__ == '__main__':
    raise SystemExit(main())
