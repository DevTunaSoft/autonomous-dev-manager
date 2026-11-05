"""Local analysis that decides what the MODEL is shown (ADM-051).

Hard rule: nothing in this module may reduce what is TESTED or RECORDED. It only
chooses what the model reads. The caller keeps the full test output on disk, every
failing test id is always named in the view the model gets, and the pass/fail gate
stays with the test runner. A model's opinion never replaces a passing test.
"""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

from .engine import SafetyError, inside

MAX_FAILING_IDS = 200
_HEADER = re.compile(r'^(FAIL|ERROR): (\S+) \(([^)]*)\)', re.M)
_PYTEST = re.compile(r'^(?:FAILED|ERROR) (\S+::\S+)', re.M)
_FRAME = re.compile(r'File "([^"]+)", line (\d+)')
_ERROR_LINE = re.compile(r'^[\w.]*(?:Error|Exception|Failure|Exit)\b.*$', re.M)
_PLACEHOLDER = re.compile(
    r'(?i)(#\s*(?:\.\.\.|rest|remaining|other|existing)\b[^\n]*'
    r'(?:unchanged|same|omitted|as before|here|code))|(\.\.\.\s*(?:existing|rest of|remaining)\b)')


def failing_tests(output: str) -> list[str]:
    """Every failing or erroring test id found in unittest or pytest output."""
    found: list[str] = []
    for match in _HEADER.finditer(output):
        found.append(match.group(3))
    for match in _PYTEST.finditer(output):
        found.append(match.group(1))
    seen, unique = set(), []
    for name in found:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    return unique


def _collapse_repeats(lines: list[str]) -> list[str]:
    out: list[str] = []
    index = 0
    while index < len(lines):
        run = 1
        while index + run < len(lines) and lines[index + run] == lines[index]:
            run += 1
        out.append(lines[index] if run == 1 else f'{lines[index]}   [repeated {run} times]')
        index += run
    return out


def _squeeze(text: str, limit: int) -> str:
    """Keep the head and the tail of a block; the tail of a traceback matters most."""
    if len(text) <= limit:
        return text
    keep_tail = int(limit * 0.7)
    keep_head = max(0, limit - keep_tail - 40)
    cut = len(text) - keep_head - keep_tail
    return f'{text[:keep_head]}\n...[{cut} characters omitted]...\n{text[-keep_tail:]}'


def excerpt_failure(output: str, max_chars: int = 3000, saved_to: str = '') -> dict:
    """Return a bounded view of a failing run for the model, plus honest accounting.

    The view always begins with the complete list of failing test ids, so shortening
    can never hide a failure. ``saved_to`` names where the full output is kept.
    """
    total = len(output)
    ids = failing_tests(output)
    listed = ids[:MAX_FAILING_IDS]
    header = ''
    if ids:
        more = f' (+{len(ids) - len(listed)} more)' if len(ids) > len(listed) else ''
        header = f'Failing tests ({len(ids)}): ' + ', '.join(listed) + more + '\n'
    if total <= max_chars:
        view = output
    else:
        lines = _collapse_repeats(output.splitlines())
        collapsed = '\n'.join(lines)
        budget = max(400, max_chars - len(header) - 120)
        if len(collapsed) <= budget:
            view = collapsed
        else:
            blocks = re.split(r'(?m)^={20,}\n', collapsed)
            bad = [b for b in blocks if _HEADER.match(b) or b.startswith(('FAIL', 'ERROR'))]
            tail_lines = [ln for ln in lines[-8:] if ln.strip()]
            tail = '\n'.join(tail_lines)
            if bad:
                room = max(300, (budget - len(tail)) // len(bad))
                view = '\n'.join(_squeeze(b.strip('\n'), room) for b in bad) + '\n' + tail
            else:
                view = _squeeze(collapsed, budget)
    where = f' Full output saved at {saved_to}.' if saved_to else ''
    omitted = max(0, total - len(view))
    note = f'[Shown {len(view)} of {total} characters.{where}]\n' if omitted else ''
    text = header + note + view
    return {'text': text, 'total_chars': total, 'shown_chars': len(view),
            'omitted_chars': omitted, 'failing_tests': ids,
            'all_failures_named': all(name in text for name in listed)}


def traceback_files(output: str, root: Path) -> list[str]:
    """Project-relative files named in tracebacks, deepest (last) frame first."""
    root = Path(root).resolve()
    order: list[str] = []
    for match in _FRAME.finditer(output):
        raw = match.group(1)
        try:
            path = Path(raw)
            if not path.is_absolute():
                path = root / path
            path = path.resolve()
            if not inside(path, root) or not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
        except (OSError, ValueError):
            continue
        if rel in order:
            order.remove(rel)
        order.append(rel)
    order.reverse()
    return order


def failure_signature(output: str) -> str:
    """Stable fingerprint of WHY a run failed, used to notice repeated dead ends."""
    ids = sorted(failing_tests(output))
    errors = sorted({re.sub(r'0x[0-9a-fA-F]+', '0x?', line.strip())
                     for line in _ERROR_LINE.findall(output)})[:20]
    digest = hashlib.sha256(json.dumps([ids, errors]).encode('utf-8')).hexdigest()
    return digest[:16]


def patch_files(patch: dict) -> list[dict]:
    """Validate the SHAPE of a model-produced patch and return its file items.

    The patch comes from model output, so it may be any JSON value. This never
    trusts it: a malformed envelope or item raises SafetyError (a handled
    condition) rather than crashing a caller with KeyError/TypeError. Path
    safety and size limits are enforced separately by ollama_direct.apply_patch.
    """
    if not isinstance(patch, dict) or not isinstance(patch.get('files'), list):
        raise SafetyError('Invalid patch envelope')
    for item in patch['files']:
        if (not isinstance(item, dict) or 'path' not in item or 'content' not in item
                or not isinstance(item['path'], str) or not isinstance(item['content'], str)):
            raise SafetyError('Invalid file replacement')
    return patch['files']


def patch_key(patch: dict) -> str:
    files = sorted((f['path'], f['content']) for f in patch_files(patch))
    return hashlib.sha256(json.dumps(files).encode('utf-8')).hexdigest()


class AttemptLedger:
    """Remembers what was tried so the loop never repeats a failed approach."""

    def __init__(self) -> None:
        self._patches: dict[str, int] = {}
        self._signatures: list[str] = []
        self._notes: list[str] = []

    def seen_patch(self, patch: dict) -> int | None:
        return self._patches.get(patch_key(patch))

    def record(self, number: int, patch: dict | None, failure_output: str, changed: list[str]) -> None:
        if patch is not None:
            self._patches[patch_key(patch)] = number
        self._signatures.append(failure_signature(failure_output))
        errors = _ERROR_LINE.findall(failure_output)
        last = errors[-1].strip()[:160] if errors else 'tests still failed'
        files = ', '.join(changed) if changed else 'no files'
        self._notes.append(f'Attempt {number} changed {files} and did NOT fix it ({last}).')

    def add_note(self, text: str) -> None:
        self._notes.append(text)

    def stuck(self) -> bool:
        """True when the last two attempts ended with the very same failure."""
        return len(self._signatures) >= 2 and self._signatures[-1] == self._signatures[-2]

    def notes(self) -> str:
        if not self._notes:
            return ''
        return ('Earlier attempts (do not repeat them; try a different approach):\n'
                + '\n'.join(self._notes[-4:]) + '\n')


def check_patch(root: Path, patch: dict, shown_in_full: set[str]) -> None:
    """Reject patches that are certainly wrong, before they touch any file."""
    root = Path(root)
    for item in patch_files(patch):
        name, content = item['path'], item['content']
        if name not in shown_in_full:
            raise SafetyError(f'{name} was not shown to the model in full; refusing to replace it')
        if not content.strip():
            raise SafetyError(f'{name}: empty replacement refused')
        current = (root / name).read_text(encoding='utf-8', errors='replace')
        if content == current:
            raise SafetyError(f'{name}: replacement is identical to the current file (no change)')
        if len(current) >= 400 and len(content) < 0.3 * len(current):
            raise SafetyError(f'{name}: replacement deletes most of the file; likely truncated')
        if _PLACEHOLDER.search(content):
            raise SafetyError(f'{name}: replacement contains a placeholder instead of real code')


def build_repair_prompt(requirements: str, failure_view: str, attempt: int,
                        source_text: str, notes: str = '') -> str:
    from .agent import make_prompt
    head = make_prompt(requirements, failure_view, attempt)
    return (head + '\nReturn ONLY JSON of the form '
            '{"files":[{"path":"existing.py","content":"complete replacement Python source"}]}. '
            'No markdown, no test edits, no shell commands. Only files shown in full below may be '
            'changed, and each must be returned complete.\n'
            + (notes + '\n' if notes else '') + source_text)
