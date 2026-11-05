"""Read-only, loopback-only Ollama health and installed-model inspection.

No cloud requests, proxy usage, redirects, model downloads, or paid APIs.
"""
from __future__ import annotations
import argparse
import json
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from .engine import SafetyError
from .ollama_direct import DEFAULT_ENDPOINT, _LOCAL_OPENER


def inspect_ollama(*, endpoint=DEFAULT_ENDPOINT, timeout=5):
    parsed = urlsplit(endpoint)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
            or parsed.username or parsed.password or parsed.path or parsed.query
            or parsed.fragment or not parsed.port):
        raise SafetyError('Ollama health checks require an explicit 127.0.0.1 HTTP endpoint')
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 30:
        raise SafetyError('Health check timeout must be 0-30 seconds')
    req = urllib.request.Request(endpoint + '/api/tags', method='GET')
    try:
        with _LOCAL_OPENER.open(req, timeout=timeout) as response:
            if response.status != 200:
                raise SafetyError('Ollama health endpoint returned a non-200 response')
            raw = response.read(1_000_001)
    except (OSError, TimeoutError, urllib.error.HTTPError) as exc:
        raise SafetyError('Local Ollama is unavailable or rejected the health check: ' + str(exc)) from exc
    if len(raw) > 1_000_000:
        raise SafetyError('Ollama health response exceeds 1 MB')
    try:
        body = json.loads(raw)
        models = body['models']
        if not isinstance(models, list):
            raise ValueError('models must be a list')
        names = []
        for model in models:
            name = model['name']
            if not isinstance(name, str) or not name or len(name) > 256:
                raise ValueError('invalid model name')
            names.append(name)
    except (ValueError, KeyError, TypeError, RecursionError) as exc:
        raise SafetyError('Ollama health response has invalid model metadata') from exc
    return {'reachable': True, 'endpoint': endpoint, 'installed_models': sorted(set(names)),
            'model_count': len(set(names)), 'inference_verified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Inspect local Ollama without sending source code')
    parser.add_argument('--endpoint', default=DEFAULT_ENDPOINT)
    args = parser.parse_args(argv)
    try:
        result = inspect_ollama(endpoint=args.endpoint)
    except SafetyError as exc:
        print(json.dumps({'reachable': False, 'error': str(exc), 'inference_verified': False}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
