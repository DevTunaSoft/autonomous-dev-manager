"""ADM-053 adversarial round 29: workflow role and skill prompt boundaries."""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adm.engine import SafetyError
from adm.skills import select_guidance

errors = []
checked = 0
rng = random.Random(53029)

for stage in ('planning', 'testing', 'repair'):
    for budget in (300, 500, 950, 2000):
        for index in range(250):
            alphabet = 'network files backup race security windows 🧪\x00\n[]{}\\/?<>\t'
            attack = ''.join(rng.choice(alphabet) for _ in range(rng.randrange(200)))
            attack += ' INJECT_THIS_SECRET_53'
            try:
                first = select_guidance(stage, attack, max_chars=budget)
                second = select_guidance(stage, attack, max_chars=budget)
                assert first == second, 'guidance not deterministic'
                assert len(first) <= budget, 'guidance exceeded context budget'
                assert 'INJECT_THIS_SECRET_53' not in first, 'injected content leaked'
                assert '\x00' not in first, 'control character leaked'
                assert first.startswith('WORKFLOW ROLE:'), 'trusted role missing'
                checked += 1
            except BaseException as exc:
                errors.append(f'{stage}/{budget}/{index}: {type(exc).__name__}: {exc}')

for stage in ('planning', 'testing', 'repair', 'invalid', '', None, 10):
    for budget in (-1, 0, 5, 239, 4097, None, True, '600', 600.0):
        try:
            select_guidance(stage, 'file security', max_chars=budget)
            errors.append(f'accepted invalid combination {stage!r} / {budget!r}')
        except SafetyError:
            checked += 1
        except BaseException as exc:
            errors.append(f'unexpected error {stage!r} / {budget!r}: {type(exc).__name__}')

print(f'ADM-053 skill adversarial checks={checked}, errors={len(errors)}')
for item in errors[:20]:
    print(item)
if errors:
    raise SystemExit(1)
