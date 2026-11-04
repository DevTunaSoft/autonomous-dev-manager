import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from adm.daemon import read_status, request_stop, serve


class DaemonLifecycleTests(unittest.TestCase):
    def test_status_unknown_before_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(read_status(tmp)['state'], 'unknown')

    def test_heartbeat_and_graceful_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'queue'
            errors = []
            def worker():
                try:
                    serve(state, poll_interval=.05, job_timeout=3)
                except Exception as exc:
                    errors.append(exc)
            t = threading.Thread(target=worker)
            t.start()
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if read_status(state)['state'] == 'running':
                        break
                    time.sleep(.02)
                self.assertEqual(read_status(state)['state'], 'running')
                self.assertIn('heartbeat_at', read_status(state))
                request_stop(state)
                t.join(5)
                self.assertFalse(t.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(read_status(state)['state'], 'stopped')
                self.assertFalse((state / 'stop-request.json').exists())
            finally:
                request_stop(state)
                t.join(5)

    def test_max_cycles_stops_and_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(serve(tmp, max_cycles=1, poll_interval=.05), 1)
            self.assertEqual(read_status(tmp)['cycles'], 1)
            self.assertEqual(read_status(tmp)['state'], 'stopped')

if __name__ == '__main__':
    unittest.main()
