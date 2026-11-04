"""Deterministic offline model selection from Ollama's locally installed inventory.

Never downloads models, contacts cloud services, or assumes that an installed
model has actually passed an inference test. Selection is advisory only.
"""
from __future__ import annotations
import argparse
import json
from .agent import safe_local_model
from .engine import SafetyError
from .ollama_health import inspect_ollama

# These are *preferences*, not verified benchmark scores. Prefer coding-tuned
# small models for constrained systems and larger variants when allowed.
_FAMILIES = ('qwen2.5-coder', 'qwen3-coder', 'deepseek-coder', 'codellama', 'starcoder2')


def _size(name):
    import re
    match = re.search(r'(?:^|[:\-])([0-9]+(?:\.[0-9]+)?)b(?:$|[-_])', name.lower())
    return float(match.group(1)) if match else None


def select_installed_model(models, *, ram_gib: float, preferred=None):
    """Return a safe installed model or an explicit blocker; no guessing sizes.

    RAM is physical total, not free memory. A model is eligible only when its
    size is parseable; actual inference still needs resource preflight.
    """
    if not isinstance(ram_gib, (int, float)) or not 4 <= ram_gib <= 4096:
        raise SafetyError('Invalid physical RAM capacity')
    if not isinstance(models, list) or any(not isinstance(x, str) for x in models):
        raise SafetyError('Invalid installed-model inventory')
    safe = []
    for name in models:
        try:
            safe_local_model('ollama/' + name)
        except SafetyError:
            continue
        size = _size(name)
        if size is None or size <= 0:
            continue
        # Conservative upper bounds; no claim that inference will fit.
        limit = 3.5 if ram_gib < 20 else 8 if ram_gib < 40 else 16
        if size <= limit:
            safe.append((name, size))
    if preferred is not None:
        safe_local_model(preferred)
        target = preferred.removeprefix('ollama/')
        match = next((name for name, _ in safe if name == target), None)
        if match is None:
            raise SafetyError('Preferred model is not installed or exceeds conservative RAM tier')
        chosen = match
    else:
        coding = [(name, size) for name, size in safe if any(f in name.lower() for f in _FAMILIES)]
        if not coding:
            raise SafetyError('No installed, size-known coding model fits conservative RAM tier')
        chosen = sorted(coding, key=lambda item: (-item[1], next((i for i, f in enumerate(_FAMILIES) if f in item[0].lower()), 99), item[0]))[0][0]
    return {'model': 'ollama/' + chosen, 'physical_ram_gib': ram_gib,
            'inference_verified': False, 'automatic_download': False,
            'note': 'Advisory selection only; check free RAM, model loading and actual inference before use'}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Select a locally installed coding model without downloading anything')
    parser.add_argument('--ram-gib', type=float, required=True)
    parser.add_argument('--preferred')
    args = parser.parse_args(argv)
    try:
        inventory = inspect_ollama()
        result = select_installed_model(inventory['installed_models'], ram_gib=args.ram_gib, preferred=args.preferred)
        print(json.dumps(result, indent=2))
        return 0
    except SafetyError as exc:
        print(json.dumps({'status': 'blocked', 'reason': str(exc), 'inference_verified': False}, indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
