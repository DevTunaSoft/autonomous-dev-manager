"""Local-only Ollama model readiness and bounded inference smoke benchmark.

This is not a coding-ability benchmark. Only loopback HTTP is contacted; callers
must explicitly opt in to executing a local inference. No model is downloaded.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json
import time
from urllib.request import Request, urlopen, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import URLError, HTTPError

from .setup import MODELS

BASE = 'http://127.0.0.1:11434'
MAX_RESPONSE = 1024 * 1024


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Ollama redirected request; blocked to protect local-only data')


_LOCAL_OPENER = build_opener(ProxyHandler({}), _RejectRedirects())


def _safe_open(req, timeout):
    return _LOCAL_OPENER.open(req, timeout=timeout)


@dataclass(frozen=True)
class ProbeResult:
    model: str
    status: str
    elapsed_seconds: float | None
    exact_answer: bool
    detail: str


def _request(path: str, payload: dict | None, timeout: float, opener=None) -> dict:
    if not 0 < timeout <= 180:
        raise ValueError('timeout must be between 0 and 180 seconds')
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = Request(BASE + path, data=data, headers={'Content-Type': 'application/json'},
                  method='POST' if payload is not None else 'GET')
    with (opener or _safe_open)(req, timeout=timeout) as response:
        raw = response.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError('Ollama response exceeded size limit')
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError('Ollama response must be an object')
    return result


def installed_models(*, timeout=5, opener=None) -> list[str]:
    result = _request('/api/tags', None, timeout, opener)
    models = result.get('models')
    if not isinstance(models, list):
        raise ValueError('Invalid Ollama models response')
    return [entry['name'] for entry in models
            if isinstance(entry, dict) and isinstance(entry.get('name'), str)]


def smoke_test(model: str, *, timeout=60, opener=None) -> ProbeResult:
    """Checks real local inference with a deterministic tiny prompt.

    Exact answer is a smoke signal, NOT proof of software-development ability.
    """
    if model not in MODELS.values():
        raise ValueError('Model is not in the approved local allowlist')
    start = time.monotonic()
    try:
        names = installed_models(timeout=min(timeout, 5), opener=opener)
        if model not in names:
            return ProbeResult(model, 'missing', None, False, 'Model is not installed locally')
        response = _request('/api/generate', {
            'model': model, 'prompt': 'Reply with only the word READY, uppercase, and nothing else.',
            'stream': False, 'options': {'num_predict': 16, 'temperature': 0},
            'keep_alive': '0s'
        }, timeout, opener)
        if response.get('done') is not True or not isinstance(response.get('response'), str):
            return ProbeResult(model, 'inconclusive', round(time.monotonic()-start, 3), False,
                               'No completed inference response')
        exact = response['response'].strip() == 'READY'
        return ProbeResult(model, 'passed' if exact else 'failed',
                           round(time.monotonic()-start, 3), exact,
                           'Tiny inference smoke check only; coding capability remains unverified')
    except (URLError, HTTPError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        return ProbeResult(model, 'blocked', round(time.monotonic()-start, 3), False,
                           f'Local Ollama probe failed: {type(exc).__name__}')


def benchmark_report(models: list[str], *, timeout=60, opener=None) -> dict:
    if len(models) != len(set(models)) or any(m not in MODELS.values() for m in models):
        raise ValueError('Only unique approved local models may be probed')
    return {'kind': 'local_inference_smoke_test', 'coding_capability_verified': False,
            'results': [asdict(smoke_test(m, timeout=timeout, opener=opener)) for m in models]}
