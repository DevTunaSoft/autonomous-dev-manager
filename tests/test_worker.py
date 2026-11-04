import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from adm.worker import WorkerSupervisor, pid_alive


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.a=WorkerSupervisor(self.root/'state')
        self.addCleanup(self.a.close)

    def test_real_run_and_spooled_logs(self):
        jid=self.a.add('hello',[sys.executable,'-c','print("works")'],self.root)
        result=self.a.run_once()
        self.assertEqual(result['state'],'passed')
        self.assertIn('works',result['output'])
        self.assertEqual(self.a.status()[0]['attempts'],1)
        self.assertTrue((self.root/'state'/f'job-{jid}-attempt-1.log').exists())

    def test_timeout_and_retry_bound(self):
        jid=self.a.add('hang',[sys.executable,'-c','import time;time.sleep(30)'],self.root,max_attempts=2)
        first=self.a.run_once(timeout=0.15,heartbeat_interval=0.02)
        self.assertEqual(first['state'],'pending')
        self.assertEqual(first['exit_code'],124)
        second=self.a.run_once(timeout=0.15,heartbeat_interval=0.02)
        self.assertEqual(second['state'],'failed')
        self.assertIsNone(self.a.run_once())

    def test_concurrent_claim_unique(self):
        self.a.add('first',[sys.executable,'-c','print(1)'],self.root)
        results=[]
        def claim_in_own_thread():
            sup=WorkerSupervisor(self.root/'state')
            try: results.append(sup.claim())
            finally: sup.close()
        t1=threading.Thread(target=claim_in_own_thread)
        t2=threading.Thread(target=claim_in_own_thread)
        t1.start();t2.start();t1.join();t2.join()
        self.assertEqual(sum(x is not None for x in results),1)

    def test_interrupted_dead_worker_recovered(self):
        jid=self.a.add('recover',[sys.executable,'-c','print("recovered")'],self.root)
        row=self.a.claim()
        self.assertIsNotNone(row)
        # Simulate a crashed supervisor before worker was spawned.
        self.a.db.execute("UPDATE jobs SET state='running',updated=? WHERE id=?",(time.time()-90,jid))
        self.assertEqual(self.a.recover(),[(jid,'pending')])
        self.assertEqual(self.a.run_once()['state'],'passed')

    def test_live_pid_blocks_duplicate_start(self):
        jid=self.a.add('live',[sys.executable,'-c','print(1)'],self.root)
        self.a.claim()
        self.a.db.execute("UPDATE jobs SET state='running',pid=?,updated=? WHERE id=?",(os.getpid(),time.time()-90,jid))
        self.assertEqual(self.a.recover(),[(jid,'blocked')])
        self.assertIsNone(self.a.run_once())

    def test_exhausted_after_interruption(self):
        jid=self.a.add('one',[sys.executable,'-c','print(1)'],self.root,max_attempts=1)
        self.a.claim()
        self.a.db.execute("UPDATE jobs SET state='running',updated=? WHERE id=?",(time.time()-90,jid))
        self.assertEqual(self.a.recover(),[(jid,'failed')])

    def test_recent_running_job_is_not_reclaimed(self):
        jid=self.a.add('active',[sys.executable,'-c','print(1)'],self.root)
        self.a.claim()
        self.assertEqual(self.a.recover(stale_after=30),[])
        self.assertEqual(self.a.status()[0]['state'],'starting')

    def test_ambiguous_starting_is_blocked(self):
        jid=self.a.add('ambiguous',[sys.executable,'-c','print(1)'],self.root)
        self.a.claim()
        self.a.db.execute('UPDATE jobs SET updated=? WHERE id=?',(time.time()-90,jid))
        self.assertEqual(self.a.recover(),[(jid,'blocked')])

    def test_invalid_input(self):
        with self.assertRaises(ValueError): self.a.add('bad','echo hello',self.root)
        with self.assertRaises(ValueError): self.a.add('bad',['echo'],self.root/'missing')
        with self.assertRaises(ValueError): self.a.run_once(timeout=0)

    def test_large_output_truncated_in_db(self):
        self.a.add('large',[sys.executable,'-c','print("x"*80000)'],self.root)
        result=self.a.run_once(max_output=1024)
        self.assertEqual(result['state'],'passed')
        self.assertLessEqual(len(result['output']),1024)

    @unittest.skipUnless(os.name=='posix', 'POSIX process-group termination')
    def test_timeout_kills_descendant(self):
        child_pid=self.root/'child.pid'
        code=("import subprocess,sys,time; "
              f"p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)']); "
              f"open({str(child_pid)!r},'w').write(str(p.pid)); "
              "time.sleep(20)")
        self.a.add('tree',[sys.executable,'-c',code],self.root,max_attempts=1)
        # Give a busy CI runner time to spawn the child before starting the
        # timeout clock; a missing PID file is not evidence of cleanup.
        result_holder=[]
        def run_in_own_connection():
            supervisor=WorkerSupervisor(self.root/'state')
            try:
                result_holder.append(supervisor.run_once(timeout=3.0,heartbeat_interval=0.05))
            finally:
                supervisor.close()
        t=threading.Thread(target=run_in_own_connection)
        t.start()
        try:
            deadline=time.monotonic()+2.0
            while not child_pid.exists() and time.monotonic()<deadline and t.is_alive():
                time.sleep(0.02)
            self.assertTrue(child_pid.exists(), 'child never started before deadline')
        finally:
            t.join(timeout=8)
        self.assertFalse(t.is_alive(), 'worker did not terminate')
        self.assertEqual(result_holder[0]['exit_code'],124)
        self.assertFalse(pid_alive(int(child_pid.read_text())))

if __name__=='__main__': unittest.main()
