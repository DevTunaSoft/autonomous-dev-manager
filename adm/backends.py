"""Local and optional remote model backends behind one patch-request interface (ADM-051).

Model id forms:
  ollama/<name>   Ollama on loopback (default, unchanged)
  local/<name>    any OpenAI-compatible server on loopback (Jan, LM Studio, llama.cpp ...)
  remote/<name>   an OpenAI-compatible HTTPS endpoint; refused unless the caller passes
                  allow_remote=True, which must come from an explicit user approval.
Prompts contain the user's source code, so a remote call is never made implicitly.
"""
from __future__ import annotations
import json
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from .engine import SafetyError

LOOPBACK = '127.0.0.1'
KNOWN_LOCAL_SERVERS = {'Jan': 1337, 'LM Studio': 1234, 'llama.cpp': 8080, 'Ollama': 11434}
MAX_RESPONSE = 1_000_000


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SafetyError('Model server attempted an HTTP redirect; request blocked')


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _RejectRedirects())


def safe_model(model: str, *, allow_remote: bool = False) -> tuple[str, str]:
    """Return (kind, name). Fails closed on anything unexpected."""
    if not isinstance(model, str) or '/' not in model:
        raise SafetyError('Model must be written like ollama/name or local/name')
    kind, name = model.split('/', 1)
    if kind not in ('ollama', 'local', 'remote'):
        raise SafetyError('Unknown model backend')
    if kind == 'remote' and not allow_remote:
        raise SafetyError('Remote models need explicit user approval')
    if not name or len(name) > 120 or not all(c.isalnum() or c in '._:/+-' for c in name):
        raise SafetyError('Invalid model identifier')
    return kind, name


def check_endpoint(endpoint: str, *, remote: bool = False) -> str:
    parsed = urlsplit(endpoint)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise SafetyError('Endpoint must be a bare scheme://host:port')
    if remote:
        if parsed.scheme != 'https' or not parsed.hostname:
            raise SafetyError('Remote endpoints must use https')
    elif parsed.scheme != 'http' or parsed.hostname != LOOPBACK or not parsed.port:
        raise SafetyError('Only a local loopback endpoint (http://127.0.0.1:port) is permitted')
    return endpoint.rstrip('/')


def parse_patch_text(text: str) -> dict:
    """Shared validation of the model's JSON answer."""
    try:
        answer = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise SafetyError('Model did not return valid patch JSON') from exc
    if not isinstance(answer, dict) or set(answer) != {'files'} or not isinstance(answer['files'], list):
        raise SafetyError('Invalid patch envelope')
    return answer


def _post(url: str, payload: dict, headers: dict, timeout: int) -> bytes:
    request = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'),
                                     headers={'Content-Type': 'application/json', **headers}, method='POST')
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise SafetyError('Model server returned an HTTP error')
            raw = response.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as exc:
        raise SafetyError(f'Model server rejected the request: HTTP {exc.code}') from exc
    except (OSError, TimeoutError) as exc:
        raise SafetyError(f'Model server request failed: {exc}') from exc
    if len(raw) > MAX_RESPONSE:
        raise SafetyError('Model response too large')
    return raw


def request_json_openai(model: str, prompt: str, *, endpoint: str, timeout: int = 300,
                        api_key: str = '', allow_remote: bool = False, num_ctx: int = 8192) -> object:
    """JSON answer from an OpenAI-compatible server; the caller validates its shape."""
    kind, name = safe_model(model, allow_remote=allow_remote)
    if kind == 'ollama':
        raise SafetyError('Use the Ollama request path for ollama/ models')
    if not 1 <= timeout <= 600:
        raise SafetyError('Invalid inference timeout')
    base = check_endpoint(endpoint, remote=(kind == 'remote'))
    headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
    body = {'model': name, 'temperature': 0, 'stream': False,
            'messages': [{'role': 'user', 'content': prompt}]}
    try:
        raw = _post(base + '/v1/chat/completions', {**body, 'response_format': {'type': 'json_object'}},
                    headers, timeout)
    except SafetyError as exc:
        if 'HTTP 400' not in str(exc) and 'HTTP 422' not in str(exc):
            raise
        raw = _post(base + '/v1/chat/completions', body, headers, timeout)   # server lacks JSON mode
    try:
        content = json.loads(raw)['choices'][0]['message']['content']
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise SafetyError('Model server answer had an unexpected shape') from exc
    try:
        return json.loads(_strip_fence(content))
    except (ValueError, TypeError) as exc:
        raise SafetyError('Model did not return valid patch JSON') from exc


def request_patch_openai(model: str, prompt: str, **kwargs) -> dict:
    content = request_json_openai(model, prompt, **kwargs)
    return parse_patch_text(json.dumps(content))


def _strip_fence(content: str) -> str:
    """Some servers wrap JSON in a markdown fence even when told not to."""
    text = content.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1] if '\n' in text else ''
        if text.rstrip().endswith('```'):
            text = text.rstrip()[:-3]
    return text.strip()


def make_generator(model: str, *, endpoint: str = '', api_key: str = '', allow_remote: bool = False):
    """Build a (model, prompt, timeout) -> patch callable marked as a real network generator."""
    kind, _ = safe_model(model, allow_remote=allow_remote)
    if kind == 'ollama':
        from .ollama_direct import request_patch, DEFAULT_ENDPOINT
        def generate(model_id, prompt, timeout=300):
            return request_patch(model_id, prompt, endpoint=endpoint or DEFAULT_ENDPOINT, timeout=timeout)
    else:
        if not endpoint:
            raise SafetyError('An endpoint is required for local/ and remote/ models')
        check_endpoint(endpoint, remote=(kind == 'remote'))
        def generate(model_id, prompt, timeout=300):
            return request_patch_openai(model_id, prompt, endpoint=endpoint, timeout=timeout,
                                        api_key=api_key, allow_remote=allow_remote)
    generate.adm_live_generator = True
    generate.adm_backend = kind
    return generate


def make_json_generator(model: str, *, endpoint: str = '', api_key: str = ''):
    """(model, prompt, timeout) -> any JSON value, local models only (plans never leave this PC)."""
    kind, _ = safe_model(model)
    if kind == 'ollama':
        from .ollama_direct import request_json, DEFAULT_ENDPOINT
        def generate(model_id, prompt, timeout=300):
            return request_json(model_id, prompt, endpoint=endpoint or DEFAULT_ENDPOINT, timeout=timeout)
    else:
        if not endpoint:
            raise SafetyError('An endpoint is required for local/ models')
        check_endpoint(endpoint)
        def generate(model_id, prompt, timeout=300):
            return request_json_openai(model_id, prompt, endpoint=endpoint, timeout=timeout, api_key=api_key)
    generate.adm_live_generator = True
    return generate


def probe_local_servers(ports: dict | None = None, timeout: float = 1.5) -> list[dict]:
    """Find OpenAI-compatible servers already running on this PC (loopback only)."""
    found = []
    for label, port in (ports or KNOWN_LOCAL_SERVERS).items():
        url = f'http://{LOOPBACK}:{port}/v1/models'
        try:
            with _OPENER.open(urllib.request.Request(url), timeout=timeout) as response:
                data = json.loads(response.read(MAX_RESPONSE))
            models = [m.get('id') for m in data.get('data', []) if isinstance(m, dict) and m.get('id')]
            found.append({'server': label, 'endpoint': f'http://{LOOPBACK}:{port}', 'models': models[:50]})
        except (OSError, ValueError, TimeoutError, AttributeError):
            continue
    return found
