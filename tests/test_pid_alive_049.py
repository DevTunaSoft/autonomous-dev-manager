import subprocess, sys, time, unittest
from adm.worker import pid_alive


class PidAliveTests(unittest.TestCase):
    def test_checking_a_live_process_must_not_kill_it(self):
        # On Windows os.kill(pid, 0) calls TerminateProcess, so a "liveness check"
        # would kill the process (or an unrelated process if the PID was reused).
        proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        try:
            time.sleep(0.5)
            self.assertTrue(pid_alive(proc.pid))
            time.sleep(0.5)
            self.assertIsNone(proc.poll(), 'pid_alive() terminated the process it was checking')
            self.assertTrue(pid_alive(proc.pid))
        finally:
            proc.kill()
            proc.wait()

    def test_dead_process_is_reported_dead(self):
        proc = subprocess.Popen([sys.executable, '-c', 'pass'])
        proc.wait()
        self.assertFalse(pid_alive(proc.pid))

    def test_invalid_pids(self):
        for value in (None, 0, -5, '12', True and 0):
            self.assertFalse(pid_alive(value))


if __name__ == '__main__':
    unittest.main()
