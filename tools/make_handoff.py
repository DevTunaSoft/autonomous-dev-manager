"""Build a master handoff so it costs no effort and cannot drift from the code.

    python tools/make_handoff.py --front handoff-front-051.md --previous HANDOFF-050-MASTER.md \
        --out HANDOFF-051-MASTER.md --append STACK-SURVEY-051.md --append STACK-COVERAGE-ANALYSIS-050.md

The hand-written front matter carries the claims; everything else (source inventory, test
inventory with counts, embedded earlier handoffs and research) is generated from the repository.
"""
import argparse
import ast
from pathlib import Path


def first_doc_line(path: Path) -> str:
    try:
        doc = ast.get_docstring(ast.parse(path.read_text(encoding='utf-8', errors='replace')))
    except SyntaxError:
        return '(does not parse)'
    return (doc or '').strip().splitlines()[0] if doc else ''


def inventory(folder: Path, title: str) -> str:
    rows = [f'## {title}', '', '| File | Lines | First docstring line |', '|---|---:|---|']
    total = 0
    for path in sorted(folder.glob('*.py')):
        lines = len(path.read_text(encoding='utf-8', errors='replace').splitlines())
        total += lines
        rows.append(f'| `{folder.name}/{path.name}` | {lines} | {first_doc_line(path)} |')
    rows += ['', f'Total: {len(list(folder.glob("*.py")))} files, {total} lines.', '']
    return '\n'.join(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    parser.add_argument('--front', required=True)
    parser.add_argument('--previous', required=True)
    parser.add_argument('--previous-title', default='')
    parser.add_argument('--out', required=True)
    parser.add_argument('--append', action='append', default=[])
    args = parser.parse_args()
    root = Path(args.root)
    parts = [(root / args.front).read_text(encoding='utf-8').rstrip() + '\n',
             inventory(root / 'adm', 'Complete current source inventory (generated)'),
             inventory(root / 'tests', 'Complete current test inventory (generated)')]
    for name in args.append:
        parts.append(f'\n---\n\n# Appendix (verbatim): {name}\n\n'
                     + (root / name).read_text(encoding='utf-8').rstrip() + '\n')
    prev = args.previous_title or f'prior master handoff: {args.previous}'
    parts.append(f'\n---\n\n# Complete {prev} (verbatim)\n\n'
                 + (root / args.previous).read_text(encoding='utf-8').rstrip() + '\n')
    (root / args.out).write_text('\n'.join(parts), encoding='utf-8', newline='\n')
    print(f'wrote {args.out}')


if __name__ == '__main__':
    main()
