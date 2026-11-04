"""Read-only diagnostics for local-only Ollama / OpenCode availability."""
from __future__ import annotations
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from .core import resources, mode
from .agent import safe_local_model
from .ollama_direct import _LOCAL_OPENER


def local_preflight(model='ollama/qwen2.5-coder:3b', endpoint='http://127.0.0.1:11434'):
    model = safe_local_model(model)
    if endpoint != 'http://127.0.0.1:11434':
        raise ValueError('Only the local default Ollama endpoint is supported by this proof')
    hardware = resources()
    result = {'hardware': hardware, 'resource_mode': mode(hardware), 'model': model,
              'opencode': {'installed': False, 'version': None},
              'ollama': {'reachable': False, 'model_installed': False, 'models': []},
              'ready': False, 'problems': []}
    binary = shutil.which('opencode')
    if binary:
        result['opencode']['installed'] = True
        try:
            proc = subprocess.run([binary, '--version'], capture_output=True, text=True,
                                  timeout=8, check=False)
            if proc.returncode == 0:
                result['opencode']['version'] = (proc.stdout or proc.stderr).strip()[:250]
            else:
                result['problems'].append('OpenCode version command failed')
        except (OSError, subprocess.TimeoutExpired):
            result['problems'].append('OpenCode could not be executed')
    else:
        result['problems'].append('OpenCode is not installed')
    try:
        with _LOCAL_OPENER.open(endpoint + '/api/tags', timeout=2) as response:
            data = json.load(response)
        names = [entry['name'] for entry in data.get('models', []) if isinstance(entry, dict) and isinstance(entry.get('name'), str)]
        result['ollama']['reachable'] = True
        result['ollama']['models'] = names
        requested = model.removeprefix('ollama/')
        result['ollama']['model_installed'] = requested in names or (':' not in requested and requested + ':latest' in names)
        if not result['ollama']['model_installed']:
            result['problems'].append('Requested local Ollama model is not installed')
    except (OSError, ValueError, urllib.error.URLError, TimeoutError):
        result['problems'].append('Local Ollama endpoint is not responding')
    result['ready'] = (result['opencode']['installed'] and result['opencode']['version'] is not None
                       and result['ollama']['reachable'] and result['ollama']['model_installed'])
    return result
