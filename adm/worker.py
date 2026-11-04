"""ADM-005 durable single-owner worker supervision for TRUSTED commands.

Not an OS sandbox or a reboot autorun service. Running processes are reclaimed
only after the previous owner is demonstrably gone; never reset live workers.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
import uuid

DDL = '''
CREATE TABLE IF NOT EXISTS jobs (
 id INTEGER PRIMARY KEY, label TEXT NOT NULL, argv TEXT NOT NULL, cwd TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
 max_attempts INTEGER NOT NULL, pid INTEGER, owner TEXT,
 heartbeat REAL, started REAL, updated REAL NOT NULL,
 exit_code INTEGER, output TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS job_events (
 id INTEGER PRIMARY KEY, job_id INTEGER, kind TEXT NOT NULL,
 payload TEXT NOT NULL, timestamp REAL NOT NULL);
'''
FINAL = {'passed','failed','blocked'}


def _windows_pid_alive(pid: int) -> bool:
    """Probe a PID without signalling it.

    os.kill(pid, 0) must NOT be used on Windows: signal 0 is CTRL_C_EVENT, so it
    sends Ctrl+C to the process group (found by Windows CI: it interrupted the
    test runner itself).
    """
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    PROCESS_QUERY_LIMITED_INFORMATION, STILL_ACTIVE = 0x1000, 259
    ERROR_ACCESS_DENIED = 5
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        # Access denied means the process exists but belongs to someone else.
        return ctypes.get_last_error() == ERROR_ACCESS_DENIED
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True  # cannot tell: fail safe (treat as alive -> job is blocked, not replayed)
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def pid_alive(pid: int | None) -> bool:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    if os.name == 'nt':
        return _windows_pid_alive(pid)
    try:
        if Path(f'/proc/{pid}/stat').exists():
            stat = Path(f'/proc/{pid}/stat').read_text()
            if stat.rsplit(')', 1)[-1].split()[0] == 'Z':
                return False
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def terminate_tree(proc: subprocess.Popen, grace: float = 1.0):
    """Terminate dedicated process group; never kill a group of unknown ownership."""
    if proc.poll() is not None:
        return
    if os.name == 'nt':
        # taskkill /T /F is necessary to stop descendants on Windows.
        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                       capture_output=True, timeout=8, check=False)
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            proc.kill()
    else:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=5)


class WorkerSupervisor:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.directory / 'jobs.sqlite', timeout=20, isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA busy_timeout=20000')
        self.db.executescript(DDL)
        self.owner = uuid.uuid4().hex

    def event(self, job_id, kind, **details):
        self.db.execute('INSERT INTO job_events(job_id,kind,payload,timestamp) VALUES(?,?,?,?)',
                        (job_id,kind,json.dumps(details),time.time()))

    def add(self, label, argv, cwd, max_attempts=2):
        if not isinstance(argv,(list,tuple)) or not argv or not all(isinstance(x,str) and x for x in argv):
            raise ValueError('command must be a nonempty list of argument strings')
        if not isinstance(max_attempts,int) or not 1 <= max_attempts <= 10:
            raise ValueError('max_attempts must be 1..10')
        path = Path(cwd).resolve()
        if not path.is_dir():
            raise ValueError('working directory must exist')
        cur = self.db.execute('INSERT INTO jobs(label,argv,cwd,max_attempts,updated) VALUES(?,?,?,?,?)',
                              (label,json.dumps(list(argv)),str(path),max_attempts,time.time()))
        self.event(cur.lastrowid,'enqueued')
        return cur.lastrowid

    def claim(self):
        """Only one supervisor can atomically claim a particular pending task."""
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute("SELECT id,argv,cwd,attempts,max_attempts FROM jobs WHERE state='pending' ORDER BY id LIMIT 1").fetchone()
            if row:
                self.db.execute("UPDATE jobs SET state='starting',owner=?,updated=?,attempts=attempts+1 WHERE id=?",
                                (self.owner,time.time(),row[0]))
                self.event(row[0],'claimed',owner=self.owner,attempt=row[3]+1)
            self.db.execute('COMMIT')
            return row
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def recover(self, stale_after=30.0):
        """Conservatively classify interrupted starts/runs. Never blindly reset live PIDs."""
        records = self.db.execute("SELECT id,state,pid,attempts,max_attempts,updated FROM jobs WHERE state IN ('starting','running')").fetchall()
        changes=[]
        for job_id,state,pid,attempts,maximum,updated in records:
            if time.time() - updated < stale_after:
                continue  # Actively heartbeating jobs are never reclaimed.
            # A started PID may still be alive after the GUI/supervisor vanished.
            # PID reuse is possible, therefore a live PID must cause a BLOCKED state,
            # rather than an unsafe kill or duplicate spawn.
            if state == "starting" and not pid:
                new = "blocked"
                reason = "Crash during spawn window; launch status cannot be proven safe to replay"
            elif pid_alive(pid):
                new = 'blocked'
                reason = 'Previously owned PID is alive or reused; inspect manually before retry'
            else:
                new = 'pending' if attempts < maximum else 'failed'
                reason = 'Interrupted task has no live recorded process; safe to retry trusted idempotent task only'
            self.db.execute("UPDATE jobs SET state=?,owner=NULL,pid=NULL,updated=?,error=? WHERE id=? AND state=?",
                            (new,time.time(),reason,job_id,state))
            self.event(job_id,'recovered',previous=state,current=new,reason=reason)
            changes.append((job_id,new))
        return changes

    def resolve_blocked(self, job_id, action):
        """Operator decision for a 'blocked' job: 'retry' (only if its old PID is gone) or 'fail'."""
        if action not in ('retry', 'fail'):
            raise ValueError("action must be 'retry' or 'fail'")
        row = self.db.execute("SELECT state,pid,attempts,max_attempts FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row or row[0] != 'blocked':
            raise ValueError('job is not blocked')
        state, pid, attempts, maximum = row
        if action == 'retry':
            if pid_alive(pid):
                raise ValueError('previous process is still alive; refusing to start a duplicate')
            if attempts >= maximum:
                raise ValueError('no attempts remaining; fail it or raise max_attempts')
            new = 'pending'
        else:
            new = 'failed'
        self.db.execute("UPDATE jobs SET state=?,owner=NULL,pid=NULL,updated=?,error=? WHERE id=? AND state='blocked'",
                        (new, time.time(), f'Operator chose {action} for blocked job', job_id))
        self.event(job_id, 'operator_resolved', action=action, current=new)
        return new

    def run_once(self, timeout=20, heartbeat_interval=0.2, max_output=30000, admission=None):
        if timeout <= 0 or timeout > 3600 or heartbeat_interval <= 0:
            raise ValueError('invalid timeouts')
        row=self.claim()
        if not row:
            return None
        job_id,raw,cwd,attempts,maximum=row
        # A fresh admission decision immediately before spawning.
        if admission is not None:
            try:
                decision = admission()
                permitted, reason = decision.allowed, decision.reason
            except Exception as exc:
                permitted, reason = False, f'Admission probe failed: {type(exc).__name__}'
            if not permitted:
                self.db.execute("UPDATE jobs SET state='pending',owner=NULL,attempts=attempts-1,updated=?,error=? WHERE id=? AND owner=? AND state='starting'", (time.time(),reason,job_id,self.owner))
                self.event(job_id,'deferred',reason=reason)
                return {'id':job_id,'state':'deferred','exit_code':None,'output':'','error':reason}
        proc=None
        output=''
        code=127
        error=None
        started=time.monotonic()
        # Output is spooled to disk, not an unbounded in-memory pipe.
        log_path=self.directory / f'job-{job_id}-attempt-{attempts+1}.log'
        try:
            with log_path.open('wb') as log:
                proc=subprocess.Popen(json.loads(raw),cwd=cwd,stdin=subprocess.DEVNULL,
                                      stdout=log,stderr=subprocess.STDOUT,shell=False,
                                      creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0),
                                      start_new_session=(os.name!='nt'))
                self.db.execute("UPDATE jobs SET state='running',pid=?,heartbeat=?,started=?,updated=? WHERE id=? AND owner=?",
                                (proc.pid,time.time(),time.time(),time.time(),job_id,self.owner))
                self.event(job_id,'started',pid=proc.pid)
                while proc.poll() is None:
                    if time.monotonic()-started >= timeout:
                        error=f'Worker exceeded {timeout}s deadline'
                        terminate_tree(proc)
                        break
                    time.sleep(min(heartbeat_interval,0.5))
                    self.db.execute('UPDATE jobs SET heartbeat=?,updated=? WHERE id=? AND owner=?',
                                    (time.time(),time.time(),job_id,self.owner))
                code=124 if error else proc.wait()
        except OSError as exc:
            error=f'Failed to start worker: {exc}'
            code=127
        finally:
            if proc is not None and proc.poll() is None:
                terminate_tree(proc)
            if log_path.exists():
                with log_path.open('rb') as f:
                    f.seek(max(0,log_path.stat().st_size-max_output))
                    output=f.read().decode('utf-8','replace')
            next_state='passed' if code==0 else ('pending' if attempts+1 < maximum else 'failed')
            self.db.execute('''UPDATE jobs SET state=?,pid=NULL,owner=NULL,exit_code=?,output=?,error=?,updated=?
                            WHERE id=? AND owner=?''',
                            (next_state,code,output,error,time.time(),job_id,self.owner))
            self.event(job_id,'finished',state=next_state,exit_code=code,error=error)
        return {'id':job_id,'state':next_state,'exit_code':code,'output':output,'error':error}

    def status(self):
        return [{'id':r[0],'label':r[1],'state':r[2],'attempts':r[3],
                 'pid':r[4],'exit_code':r[5],'error':r[6]}
                for r in self.db.execute('SELECT id,label,state,attempts,pid,exit_code,error FROM jobs ORDER BY id')]

    def close(self):
        self.db.close()
