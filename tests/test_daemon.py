import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from adm.daemon import serve
from adm.worker import WorkerSupervisor

class DaemonTests(unittest.TestCase):
    def test_waits_for_new_job_without_reprompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp)/'state'
            stop=threading.Event()
            results=[]
            errors=[]
            def work():
                try:
                    serve(state,poll_interval=.05,job_timeout=5,stop_event=stop,
                          on_result=lambda r: (results.append(r),stop.set()))
                except Exception as e: errors.append(e)
            t=threading.Thread(target=work)
            t.start()
            try:
                time.sleep(.15)
                mgr=WorkerSupervisor(state)
                try: mgr.add('later',[sys.executable,'-c','print("later")'],tmp)
                finally: mgr.close()
                t.join(timeout=5)
                self.assertFalse(t.is_alive())
                self.assertFalse(errors)
                self.assertEqual(len(results),1)
                self.assertEqual(results[0]['state'],'passed')
            finally:
                stop.set();t.join(timeout=5)

    def test_multiple_jobs_processed_without_new_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp)/'state'
            mgr=WorkerSupervisor(state)
            try:
                for i in range(3): mgr.add(str(i),[sys.executable,'-c','print(123)'],tmp)
            finally: mgr.close()
            results=[]
            cycles=serve(state,poll_interval=.05,max_cycles=3,on_result=results.append)
            self.assertEqual(cycles,3)
            self.assertEqual([r['state'] for r in results],['passed']*3)

    def test_invalid_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError): serve(tmp,poll_interval=0)
            with self.assertRaises(ValueError): serve(tmp,max_cycles=0)

    def test_stop_without_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            stop=threading.Event();stop.set()
            self.assertEqual(serve(tmp,stop_event=stop),0)
