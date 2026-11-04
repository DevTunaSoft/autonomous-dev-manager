"""Persistent unattended trusted-job runner with observable lifecycle state.

This is not an OS sandbox or a Windows startup service. A running daemon
polls the queue, writes atomic heartbeat/status, and accepts graceful stop.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import threading
import time
from .worker import WorkerSupervisor
from .engine import SafetyError
from .project_lock import exclusive_project


def _atomic_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.{threading.get_ident()}.tmp')
    try:
        temporary.write_text(json.dumps(payload, sort_keys=True), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def request_stop(state):
    """Request cooperative stop; active job finishes before shutdown."""
    state = Path(state).resolve()
    state.mkdir(parents=True, exist_ok=True)
    _atomic_json(state / 'stop-request.json', {'requested_at': time.time()})


def read_status(state):
    path = Path(state).resolve() / 'daemon-status.json'
    if not path.is_file():
        return {'state': 'unknown', 'detail': 'No daemon status recorded'}
    return json.loads(path.read_text(encoding='utf-8'))


def serve(state, *, poll_interval=1.0, job_timeout=120.0, stop_event=None,
          max_cycles=None, on_result=None):
    if not 0.05 <= poll_interval <= 300 or not 0.1 <= job_timeout <= 3600:
        raise ValueError('Invalid polling interval or job timeout')
    if max_cycles is not None and (not isinstance(max_cycles, int) or max_cycles < 1):
        raise ValueError('max_cycles must be a positive integer')
    stop_event = stop_event if stop_event is not None else threading.Event()
    state = Path(state).resolve()
    state.mkdir(parents=True, exist_ok=True)
    status_path = state / 'daemon-status.json'
    stop_path = state / 'stop-request.json'
    # Honor stop requests already present; never silently discard them at startup.
    # An OS-managed exclusive lock prevents two supervisor processes from racing to
    # recover or execute the same queue. The kernel releases it after a crash.
    with exclusive_project(state):
        return _serve_locked(state, stop_path, status_path, stop_event,
                             poll_interval, job_timeout, max_cycles, on_result)


def _serve_locked(state, stop_path, status_path, stop_event,
                  poll_interval, job_timeout, max_cycles, on_result):
    supervisor = WorkerSupervisor(state)
    cycles = 0
    last_result = None
    def update(status):
        _atomic_json(status_path, {'state': status, 'pid': os.getpid(),
                     'heartbeat_at': time.time(), 'cycles': cycles,
                     'last_result': last_result})
    try:
        supervisor.recover()
        update('running')
        while not stop_event.is_set() and not stop_path.exists():
            update('running')
            result = supervisor.run_once(timeout=job_timeout)
            if result is not None:
                last_result = result.get('state')
                if on_result is not None:
                    on_result(result)
            cycles += 1
            update('running')
            if max_cycles is not None and cycles >= max_cycles:
                break
            if result is None or result['state'] == 'deferred':
                stop_event.wait(poll_interval)
        return cycles
    finally:
        update('stopped')
        supervisor.close()
        stop_path.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description='ADM trusted unattended queue runner')
    parser.add_argument('--state', default='.adm-worker-state')
    parser.add_argument('--poll', type=float, default=1.0)
    parser.add_argument('--timeout', type=float, default=120.0)
    parser.add_argument('--status', action='store_true', help='Print latest recorded daemon state')
    parser.add_argument('--stop', action='store_true', help='Request graceful stop')
    args = parser.parse_args(argv)
    if args.status:
        print(json.dumps(read_status(args.state), indent=2)); return
    if args.stop:
        request_stop(args.state)
        print('Stop requested; current job may finish before daemon exits.'); return
    print('ADM daemon started. Press Ctrl+C to stop.', flush=True)
    try:
        serve(args.state, poll_interval=args.poll, job_timeout=args.timeout,
              on_result=lambda r: print(json.dumps(r), flush=True))
    except KeyboardInterrupt:
        print('ADM daemon stopped.', flush=True)

if __name__ == '__main__':
    main()
