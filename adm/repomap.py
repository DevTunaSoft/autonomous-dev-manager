"""Dependency-free map of a Python project, built with the standard ``ast`` module (ADM-051).

The model is shown the files that matter in full and everything else only as a short
map of names and signatures. A file is only ever editable if it was shown in full, so
the model can never be asked to return a "complete replacement" of text it did not see.
"""
from __future__ import annotations
import ast
from pathlib import Path

from .context import traceback_files, failing_tests
from .engine import SafetyError

_SKIP_DIRS = {'__pycache__', '.git', '.venv', 'venv', 'env', 'node_modules', 'build', 'dist'}
MAX_MAP_FILES = 200
MAX_MAP_CHARS = 3000


def _signature(node) -> str:
    try:
        return f'({ast.unparse(node.args)})'
    except Exception:           # unparse can fail on exotic nodes; the name is still useful
        return '(...)'


def _summarise(path: Path, root: Path) -> dict:
    rel = path.relative_to(root).as_posix()
    info = {'path': rel, 'chars': 0, 'symbols': [], 'imports': [], 'error': ''}
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError as exc:
        info['error'] = f'unreadable: {exc}'
        return info
    info['chars'] = len(text)
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError) as exc:
        info['error'] = f'does not parse (line {exc.lineno}): {exc.msg}'
        return info
    for node in tree.body:
        if isinstance(node, ast.Import):
            info['imports'] += [alias.name.split('.')[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            info['imports'].append(node.module.split('.')[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info['symbols'].append(f'def {node.name}{_signature(node)} [lines {node.lineno}-{node.end_lineno}]')
        elif isinstance(node, ast.ClassDef):
            info['symbols'].append(f'class {node.name} [lines {node.lineno}-{node.end_lineno}]')
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    info['symbols'].append(f'    def {child.name}{_signature(child)} [lines {child.lineno}-{child.end_lineno}]')
    return info


def build_map(root: Path) -> list[dict]:
    root = Path(root).resolve()
    files = []
    for path in sorted(root.rglob('*.py')):
        parts = set(path.relative_to(root).parts[:-1])
        if parts & _SKIP_DIRS or path.is_symlink():
            continue
        files.append(path)
        if len(files) >= MAX_MAP_FILES:
            break
    return [_summarise(path, root) for path in files]


def render_map(entries: list[dict], max_chars: int = MAX_MAP_CHARS) -> str:
    lines: list[str] = []
    for entry in entries:
        lines.append(f"{entry['path']}" + (f"  ({entry['error']})" if entry['error'] else ''))
        lines += [f'  {symbol}' for symbol in entry['symbols']]
    text = '\n'.join(lines)
    if len(text) > max_chars:
        text = text[:max_chars].rsplit('\n', 1)[0] + f'\n... [map shortened; {len(entries)} files in project]'
    return text


def editable_files(root: Path) -> list[str]:
    """Only existing top-level application files can be replaced (see apply_patch)."""
    root = Path(root).resolve()
    return sorted(p.name for p in root.glob('*.py')
                  if not p.name.startswith('test_') and p.is_file() and not p.is_symlink())


def _test_imports(root: Path, modules: set[str]) -> set[str]:
    """Application modules imported by the test files that are failing."""
    wanted: set[str] = set()
    for path in Path(root).glob('test_*.py'):
        if path.stem not in modules:
            continue
        try:
            tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
        except (SyntaxError, ValueError, RecursionError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                wanted |= {alias.name.split('.')[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                wanted.add(node.module.split('.')[0])
    return wanted


def select_context(root: Path, failure_output: str, budget_chars: int) -> dict:
    """Choose which files the model sees in full and which only as a map.

    Returns {'text', 'full', 'map_only'}. Raises SafetyError if a relevant file cannot
    be shown in full inside the budget, because a partial view must never be turned
    into a complete replacement.
    """
    root = Path(root).resolve()
    editable = editable_files(root)
    score = {name: 0 for name in editable}
    frames = traceback_files(failure_output, root)
    for position, rel in enumerate(frames):
        if rel in score:
            score[rel] = max(score[rel], 100 - position)
    failing_modules = {name.split('.')[0] for name in failing_tests(failure_output)}
    for module in _test_imports(root, failing_modules):
        name = module + '.py'
        if name in score:
            score[name] = max(score[name], 50)
    ranked = sorted(editable, key=lambda n: (-score[n], n))
    sizes = {n: (root / n).stat().st_size for n in editable}
    overhead = 200
    used = 0
    full: list[str] = []
    for name in ranked:
        need = sizes[name] + len(name) + 20
        if used + need <= budget_chars - MAX_MAP_CHARS // 2:
            full.append(name)
            used += need
        elif score[name] > 0 or not full:
            raise SafetyError(f'{name} is too large to show in full inside the model context; '
                              f'split it into smaller files')
    map_entries = [e for e in build_map(root) if e['path'] not in full]
    parts = []
    for name in full:
        data = (root / name).read_bytes().decode('utf-8', errors='replace')
        parts.append(f'FILE {name} (shown in full; may be replaced):\n{data}')
    others = render_map(map_entries, min(MAX_MAP_CHARS, max(0, budget_chars - used - overhead)))
    if others:
        parts.append('OTHER FILES (names only, NOT editable this attempt):\n' + others)
    return {'text': '\n'.join(parts), 'full': full,
            'map_only': [e['path'] for e in map_entries]}
