"""ADM-045 supervisor ownership regression tests."""
import tempfile
import threading
import time
import unittest
from pathlib import Path
from adm.daemon import serve
from adm.engine import SafetyError


class SupervisorSingletonTests(unittest.TestCase):
    def test_second_supervisor_rejected_while_first_owns_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'state'
            stop = threading.Event()
            errors = []
            t = threading.Thread(target=lambda: self._run(state, stop, errors))
            t.start()
            try:
                deadline = time.monotonic() + 4
                while not (state / '.adm-repair.lock').exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue((state / '.adm-repair.lock').exists())
                with self.assertRaises(SafetyError):
                    serve(state, max_cycles=1, poll_interval=.05)
            finally:
                stop.set()
                t.join(5)
            self.assertFalse(t.is_alive())
            self.assertEqual(errors, [])
            self.assertTrue((state / '.adm-repair.lock').exists())  # persistent inode prevents split-brain

    def test_orphaned_metadata_allows_crash_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'state'
            state.mkdir()
            (state / '.adm-repair.lock').write_text('orphan')
            serve(state, max_cycles=1)  # kernel lock is free; stale metadata is not ownership
            self.assertTrue((state / '.adm-repair.lock').exists())

    @staticmethod
    def _run(state, stop, errors):
        try:
            serve(state, poll_interval=.05, stop_event=stop)
        except Exception as exc:
            errors.append(exc)
