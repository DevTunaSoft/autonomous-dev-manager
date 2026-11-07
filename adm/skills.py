"""Bounded, offline workflow skills selected without extra AI requests (ADM-053).

A skill is a trusted, fixed instruction for an existing planning/testing/repair
model call. The user's request is used only for deterministic keyword matching;
its text is NEVER copied into a skill. No plugin execution, network, or file IO.
This is a prompt-guidance layer, not a claim of multi-agent execution.
"""
from __future__ import annotations

import re

from .engine import SafetyError

MAX_SCAN_CHARS = 12000
_ALLOWED_STAGES = frozenset({'planning', 'testing', 'repair'})
_BASE = {
    'planning': (
        'WORKFLOW ROLE: PLANNER. Turn the request into a small deliverable and '
        'specific observable acceptance checks. State only genuinely blocking '
        'questions. Prefer free, offline, single-app solutions; do not invent '
        'features or claim an unbuilt feature already works.'
    ),
    'testing': (
        'WORKFLOW ROLE: TEST DESIGNER. Translate each approved check into a '
        'deterministic test that fails before implementation. Include meaningful '
        'boundary conditions. Never mark unfinished behavior as passing or weaken '
        'the approved requirements.'
    ),
    'repair': (
        'WORKFLOW ROLE: IMPLEMENTER AND REVIEWER. Use the real failing-test evidence '
        'to make the smallest complete fix. Preserve public behavior, frozen tests '
        'and security boundaries. Do not retry an identical failed patch or claim '
        'success without the test runner verifying it.'
    ),
}

# Each entry is (name, whole-word triggers, supported stages, curated guidance).
# Order is intentional: a small, stable set of the strongest matches is supplied.
_SKILLS = (
    ('security', frozenset({'security', 'secure', 'password', 'credential', 'token',
                            'privacy', 'permission', 'authentication', 'authorization'}),
     frozenset({'planning', 'testing', 'repair'}),
     'SECURITY SKILL: Treat inputs and generated content as untrusted; validate '
     'boundaries and permissions; avoid leaking credentials, disabling checks, '
     'or adding remote dependencies.'),
    ('files', frozenset({'file', 'files', 'backup', 'restore', 'recovery', 'storage',
                         'database', 'sqlite', 'journal', 'save', 'write'}),
     frozenset({'planning', 'testing', 'repair'}),
     'DATA-INTEGRITY SKILL: Consider partial writes, corrupt records, repeated '
     'operations and interrupted recovery. Preserve user data; verify restores '
     'rather than reporting success on intent.'),
    ('concurrency', frozenset({'thread', 'threads', 'concurrency', 'parallel',
                               'race', 'queue', 'workers', 'process', 'processes'}),
     frozenset({'planning', 'testing', 'repair'}),
     'CONCURRENCY SKILL: Check interleavings, duplicate execution, lock ownership, '
     'timeouts and crash recovery. Do not silently replay uncertain side effects.'),
    ('desktop', frozenset({'windows', 'desktop', 'gui', 'interface', 'button',
                           'tkinter', 'exe', 'installer', 'kiosk'}),
     frozenset({'planning', 'testing', 'repair'}),
     'DESKTOP SKILL: Make actions understandable to non-programmers, provide '
     'clear error messages and support keyboard interaction. Treat a packaged '
     'Windows executable as a separate acceptance gate.'),
    ('performance', frozenset({'speed', 'fast', 'faster', 'slow', 'memory',
                               'performance', 'cpu', 'latency', 'large'}),
     frozenset({'planning', 'testing', 'repair'}),
     'RESOURCE SKILL: Prefer bounded work and reasonable CPU/RAM consumption. '
     'Measure regressions before asserting an optimization succeeded.'),
    ('network', frozenset({'network', 'internet', 'http', 'api', 'server',
                           'online', 'download', 'socket', 'web'}),
     frozenset({'planning', 'testing', 'repair'}),
     'NETWORK SKILL: Prefer offline behavior. Explicitly test timeouts, errors, '
     'oversized responses and redirect handling; do not assume remote access '
     'or silently spend paid API tokens.'),
)


def select_guidance(stage: str, request: str = '', *, max_chars: int = 950) -> str:
    """Return a deterministic, complete-line, bounded set of trusted instructions.

    Unknown stages, non-string text and unsafe budgets fail closed. Up to two
    matching skills are added, never excerpts or user-supplied instructions.
    """
    if not isinstance(stage, str) or stage not in _ALLOWED_STAGES:
        raise SafetyError('Unknown workflow stage')
    if not isinstance(request, str):
        raise SafetyError('Workflow request must be text')
    if type(max_chars) is not int or not 240 <= max_chars <= 4096:
        raise SafetyError('Invalid workflow guidance budget')
    base = _BASE[stage]
    if len(base) > max_chars:
        raise SafetyError('Workflow guidance budget too small for role')
    tokens = set(re.findall(r'[a-z0-9]+', request[:MAX_SCAN_CHARS].casefold()))
    ranked = sorted(
        ((-len(tokens & triggers), index, name, description)
         for index, (name, triggers, stages, description) in enumerate(_SKILLS)
         if stage in stages and tokens & triggers)
    )
    parts = [base]
    used = len(base)
    for _, _, _, description in ranked[:2]:
        additional = len(description) + 1
        if used + additional <= max_chars:
            parts.append(description)
            used += additional
    return '\n'.join(parts)
