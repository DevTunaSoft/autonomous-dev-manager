import sys, tempfile, threading, time, unittest
from adm.worker import WorkerSupervisor
from adm.daemon import serve, read_status, default_admission
from adm.desktop import status_summary
from adm.adaptive import Decision


class HeartbeatTests(unittest.TestCase):
    def test_heartbeat_stays_fresh_during_a_long_job(self):
        with tempfile.TemporaryDirectory() as t:
            w = WorkerSupervisor(t)
            w.add('long', [sys.executable, '-c', 'import time;time.sleep(2.5)'], t)
            w.close()
            th = threading.Thread(target=serve, args=(t,), kwargs={'poll_interval': .05, 'max_cycles': 1, 'heartbeat_interval': .2})
            th.start()
            stamps = set()
            for _ in range(20):
                time.sleep(.1)
                rec = read_status(t)
                if rec.get('state') == 'running':
                    stamps.add(rec['heartbeat_at'])
            th.join()
            self.assertGreaterEqual(len(stamps), 4, 'heartbeat did not advance while the job ran')
            self.assertEqual(read_status(t)['state'], 'stopped')

    def test_default_timeout_allows_long_ai_jobs(self):
        from adm.daemon import DEFAULT_JOB_TIMEOUT
        self.assertGreaterEqual(DEFAULT_JOB_TIMEOUT, 900)


class AdmissionTests(unittest.TestCase):
    def test_denied_admission_defers_and_keeps_job_pending(self):
        deny = lambda: Decision(False, 'test: not enough memory', 1, False, 'constrained')
        with tempfile.TemporaryDirectory() as t:
            w = WorkerSupervisor(t)
            jid = w.add('x', [sys.executable, '-c', 'print(1)'], t)
            w.close()
            seen = []
            serve(t, poll_interval=.05, max_cycles=2, admission=deny, on_result=seen.append)
            w = WorkerSupervisor(t)
            try:
                job = [j for j in w.status() if j['id'] == jid][0]
            finally:
                w.close()
            self.assertEqual(job['state'], 'pending')
            self.assertEqual(job['attempts'], 0)
            self.assertTrue(all(r['state'] == 'deferred' for r in seen))

    def test_default_admission_returns_decision(self):
        self.assertIsInstance(default_admission(), Decision)


class BlockedJobTests(unittest.TestCase):
    def _blocked(self, w, pid):
        jid = w.add('b', [sys.executable, '-c', 'pass'], '.')
        w.db.execute("UPDATE jobs SET state='blocked',pid=? WHERE id=?", (pid, jid))
        return jid

    def test_retry_when_old_process_gone(self):
        with tempfile.TemporaryDirectory() as t:
            w = WorkerSupervisor(t)
            try:
                jid = self._blocked(w, None)
                self.assertEqual(w.resolve_blocked(jid, 'retry'), 'pending')
            finally:
                w.close()

    def test_retry_refused_while_old_process_alive(self):
        import os
        with tempfile.TemporaryDirectory() as t:
            w = WorkerSupervisor(t)
            try:
                jid = self._blocked(w, os.getpid())
                with self.assertRaises(ValueError):
                    w.resolve_blocked(jid, 'retry')
                self.assertEqual(w.resolve_blocked(jid, 'fail'), 'failed')
            finally:
                w.close()

    def test_only_blocked_jobs_and_valid_actions(self):
        with tempfile.TemporaryDirectory() as t:
            w = WorkerSupervisor(t)
            try:
                jid = w.add('p', [sys.executable, '-c', 'pass'], t)
                with self.assertRaises(ValueError):
                    w.resolve_blocked(jid, 'retry')
                with self.assertRaises(ValueError):
                    w.resolve_blocked(jid, 'delete')
            finally:
                w.close()


class GuiStatusTests(unittest.TestCase):
    def test_stale_heartbeat_still_reported_unresponsive(self):
        with tempfile.TemporaryDirectory() as t:
            from adm.daemon import _atomic_json
            from pathlib import Path
            _atomic_json(Path(t) / 'daemon-status.json', {'state': 'running', 'heartbeat_at': time.time() - 60})
            self.assertEqual(status_summary(t)['state'], 'unresponsive')


if __name__ == '__main__':
    unittest.main()
