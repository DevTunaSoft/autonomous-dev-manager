import sys,tempfile,unittest
from pathlib import Path
from adm.core import Supervisor,resources,mode
class SupervisorTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.sp=Supervisor(self.root/'state')
 def tearDown(self):self.sp.close();self.tmp.cleanup()
 def test_success_and_evidence(self):
  self.sp.add('pass',[sys.executable,'-c','print("ok")'],self.root)
  result=self.sp.run_next();self.assertEqual(result['state'],'passed');self.assertIn('ok',result['output'])
  self.assertEqual(self.sp.db.execute("SELECT COUNT(*) FROM events WHERE kind='execution'").fetchone()[0],1)
 def test_failure_and_bounded_retry(self):
  self.sp.add('fail',[sys.executable,'-c','raise SystemExit(7)'],self.root,2)
  self.assertEqual(self.sp.run_next()['state'],'pending')
  self.assertEqual(self.sp.run_next()['state'],'failed')
  self.assertIsNone(self.sp.run_next())
 def test_recovery_after_restart(self):
  tid=self.sp.add('restart',[sys.executable,'-c','print("resumed")'],self.root)
  self.sp.db.execute("UPDATE tasks SET state='running' WHERE id=?",(tid,));self.sp.db.commit();self.sp.close()
  self.sp=Supervisor(self.root/'state');self.assertEqual(self.sp.run_next()['state'],'passed')
 def test_timeout(self):
  self.sp.add('timeout',[sys.executable,'-c','import time;time.sleep(3)'],self.root,1)
  self.assertEqual(self.sp.run_next(timeout=0.1)['exit_code'],124)
 def test_invalid(self):
  with self.assertRaises(ValueError):self.sp.add('bad',[],self.root)
 def test_resource_modes(self):
  self.assertIn(mode(resources()),('constrained','balanced','performance'))
  self.assertEqual(mode({'ram_available_bytes':None,'disk_free_bytes':0}),'constrained')
if __name__=='__main__':unittest.main()
