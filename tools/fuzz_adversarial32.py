"""ADM-056 fuzz round 32: corrupted recovery evidence must survive rejection."""
from __future__ import annotations

import random
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.build import _recover_interrupted
from adm.engine import SafetyError
from adm.repair_recovery import prepare_journal

random_source = random.Random(56032)
checks = 0
errors = []

with tempfile.TemporaryDirectory(prefix='adm-056-fuzz-') as temp:
    parent = Path(temp)
    for i in range(220):
        root = parent / f'project-{i}'
        root.mkdir()
        source = root / 'app.py'
        original = (f'def calculate():\n    return {i}\n').encode()
        source.write_bytes(original)
        ev = parent / f'evidence-{i}'
        ev.mkdir()

        mode = random_source.choice(('bad_json', 'bad_report', 'unknown_file', 'unexpected_change',
                                     'nested_dir', 'orphan', 'bad_journal_root'))
        if mode == 'bad_json':
            saved = bytes(random_source.randrange(256) for _ in range(random_source.randint(1, 180)))
            (ev / 'repair-journal.json').write_bytes(saved)
        elif mode == 'bad_report':
            saved = b'not a valid repair report'
            (ev / 'ollama-direct-report.json').write_bytes(saved)
        elif mode == 'unknown_file':
            saved = b'important data, no marker'
            (ev / 'ollama-direct-report.json').write_bytes(b'{}')
            (ev / 'important.txt').write_bytes(saved)
        elif mode == 'unexpected_change':
            new = f'def calculate():\n    return {i+1}\n'
            prepare_journal(root, ev, {'files': [{'path': 'app.py', 'content': new}]})
            source.write_text('def calculate():\n    return 999999\n', encoding='utf-8')
            saved = (ev / 'repair-journal.json').read_bytes()
        elif mode == 'nested_dir':
            saved = b'high-value data'
            (ev / 'important').mkdir()
            (ev / 'important' / 'data.txt').write_bytes(saved)
        elif mode == 'orphan':
            saved = b'not owned by this recovery routine'
            (ev / 'baseline-output.log').write_bytes(saved)
        else:
            prepare_journal(root, ev, {'files': [{'path': 'app.py',
                                                  'content': 'def calculate():\n    return 4\n'}]})
            journal = ev / 'repair-journal.json'
            body = journal.read_text(encoding='utf-8').replace(str(root), str(parent / 'foreign'), 1)
            journal.write_text(body, encoding='utf-8')
            saved = journal.read_bytes()
        source_before = source.read_bytes()
        try:
            _recover_interrupted(root, ev)
            errors.append(f'{mode}/{i}: unsafe cleanup returned success')
        except SafetyError:
            checks += 1
            if not ev.is_dir() or source.read_bytes() != source_before:
                errors.append(f'{mode}/{i}: evidence/source bytes lost')
            if mode == 'bad_json' and (ev / 'repair-journal.json').read_bytes() != saved:
                errors.append(f'{mode}/{i}: corrupt journal changed')
        except BaseException as exc:
            errors.append(f'{mode}/{i}: wrong exception {type(exc).__name__}: {exc}')

    for i in range(120):
        root = parent / f'good-project-{i}'
        root.mkdir()
        source = root / 'app.py'
        old = (f'original_{i}\n').encode()
        source.write_bytes(old)
        ev = parent / f'good-evidence-{i}'
        new = f'replacement_{i}\n'
        prepare_journal(root, ev, {'files': [{'path': 'app.py', 'content': new}]})
        source.write_text(new, encoding='utf-8')
        try:
            _recover_interrupted(root, ev)
            checks += 1
            if ev.exists() or source.read_bytes() != old:
                errors.append(f'valid/{i}: recovery incomplete')
        except BaseException as exc:
            errors.append(f'valid/{i}: {type(exc).__name__}: {exc}')

print(f'ADM-056 evidence-recovery fuzz checks={checks}, errors={len(errors)}')
for error in errors[:25]:
    print(error)
if errors:
    raise SystemExit(1)
