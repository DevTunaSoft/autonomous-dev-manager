"""Durable, resource-aware command verification supervisor (stdlib only)."""
import json, os, platform, sqlite3, subprocess, time, hashlib, shutil
from pathlib import Path

SCHEMA = '''CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, name TEXT NOT NULL, argv TEXT NOT NULL, cwd TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 2, exit_code INTEGER, output TEXT, updated REAL NOT NULL); CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, task_id INTEGER, kind TEXT NOT NULL, payload TEXT NOT NULL, created REAL NOT NULL);'''

def resources():
    total = available = None
    try:
        import ctypes
        if os.name == 'nt':
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong),('dwMemoryLoad', ctypes.c_ulong),('ullTotalPhys', ctypes.c_ulonglong),('ullAvailPhys', ctypes.c_ulonglong),('ullTotalPageFile', ctypes.c_ulonglong),('ullAvailPageFile', ctypes.c_ulonglong),('ullTotalVirtual', ctypes.c_ulonglong),('ullAvailVirtual', ctypes.c_ulonglong),('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
            m=MEMORYSTATUSEX();m.dwLength=ctypes.sizeof(m)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                total,available=m.ullTotalPhys,m.ullAvailPhys
        elif Path('/proc/meminfo').exists():
            lines=Path('/proc/meminfo').read_text().splitlines()
            vals={k:int(v.strip().split()[0])*1024 for k,v in (line.split(':',1) for line in lines)}
            total,available=vals.get('MemTotal'),vals.get('MemAvailable')
    except (OSError,ValueError,AttributeError):
        pass
    return {'os':platform.platform(),'cpu_count':os.cpu_count() or 1,'ram_total_bytes':total,'ram_available_bytes':available,'disk_free_bytes':shutil.disk_usage(Path.home()).free}

def mode(info):
    available=info['ram_available_bytes']
    if available is None or available < 8*1024**3 or info['disk_free_bytes'] < 10*1024**3: return 'constrained'
    if available < 20*1024**3: return 'balanced'
    return 'performance'

class Supervisor:
    def __init__(self, root):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.root/'state.sqlite', timeout=30)
        self.db.executescript(SCHEMA)
        self.db.execute("UPDATE tasks SET state='pending' WHERE state='running'")
        self.db.commit()
    def event(self, tid, kind, payload):
        self.db.execute('INSERT INTO events(task_id,kind,payload,created) VALUES(?,?,?,?)',(tid,kind,json.dumps(payload),time.time()))
    def add(self,name,argv,cwd,max_attempts=2):
        p=Path(cwd).resolve()
        if not p.is_dir():raise ValueError('Working directory does not exist')
        if not argv or not all(isinstance(x,str) and x for x in argv):raise ValueError('argv must be nonempty string array')
        if max_attempts < 1 or max_attempts > 20:raise ValueError('max_attempts must be 1..20')
        cur=self.db.execute('INSERT INTO tasks(name,argv,cwd,updated,max_attempts) VALUES(?,?,?,?,?)',(name,json.dumps(argv),str(p),time.time(),max_attempts))
        self.event(cur.lastrowid,'created',{'argv':argv});self.db.commit();return cur.lastrowid
    def run_next(self,timeout=120):
        row=self.db.execute("SELECT id,argv,cwd,attempts,max_attempts FROM tasks WHERE state='pending' ORDER BY id LIMIT 1").fetchone()
        if not row:return None
        tid,raw,cwd,attempts,max_attempts=row
        argv=json.loads(raw)
        self.db.execute("UPDATE tasks SET state='running',attempts=attempts+1,updated=? WHERE id=?",(time.time(),tid));self.db.commit()
        try:
            p=subprocess.run(argv,cwd=cwd,capture_output=True,text=True,timeout=timeout,shell=False,errors='replace')
            code=p.returncode;out=(p.stdout+'\n'+p.stderr)[-30000:]
        except subprocess.TimeoutExpired as exc:
            code=124;out=f'Timeout after {timeout} seconds: {exc}'
        except OSError as exc:
            code=127;out=f'Execution error: {exc}'
        state='passed' if code==0 else ('pending' if attempts+1 < max_attempts else 'failed')
        digest=hashlib.sha256(out.encode()).hexdigest()
        self.db.execute('UPDATE tasks SET state=?,exit_code=?,output=?,updated=? WHERE id=?',(state,code,out,time.time(),tid))
        self.event(tid,'execution',{'state':state,'exit_code':code,'output_sha256':digest,'attempt':attempts+1})
        self.db.commit();return {'id':tid,'state':state,'exit_code':code,'output':out,'attempt':attempts+1}
    def status(self):
        return [{'id':r[0],'name':r[1],'state':r[2],'attempts':r[3],'exit_code':r[4]} for r in self.db.execute('SELECT id,name,state,attempts,exit_code FROM tasks ORDER BY id')]
    def close(self):self.db.close()
