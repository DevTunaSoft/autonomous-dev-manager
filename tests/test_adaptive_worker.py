import sys
import tempfile
import unittest
from pathlib import Path
from adm.adaptive import GIB, admission_for_build
from adm.worker import WorkerSupervisor


class AdaptiveWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.worker = WorkerSupervisor(self.root / 'state')
        self.addCleanup(self.worker.close)
        self.marker = self.root / 'ran.txt'
        self.job = self.worker.add('admitted build',
            [sys.executable, '-c', f'from pathlib import Path;Path({str(self.marker)!r}).write_text("ok")'],
            self.root, max_attempts=1)

    def test_denied_is_deferred_without_consuming_attempt(self):
        calls = []
        def probe():
            calls.append(True)
            return dict(ram_available_bytes=1*GIB,disk_free_bytes=20*GIB,cpu_count=4)
        admission=lambda: admission_for_build(probe=probe,job_ram_gib=3)
        result=self.worker.run_once(admission=admission)
        self.assertEqual(result['state'],'deferred')
        self.assertEqual(self.worker.status()[0]['attempts'],0)
        self.assertFalse(self.marker.exists())
        self.assertEqual(len(calls),1)

    def test_deferred_job_runs_after_resources_recover(self):
        snapshot={'ram_available_bytes':1*GIB,'disk_free_bytes':20*GIB,'cpu_count':4}
        admission=lambda: admission_for_build(probe=lambda:snapshot.copy(),job_ram_gib=3)
        self.assertEqual(self.worker.run_once(admission=admission)['state'],'deferred')
        snapshot['ram_available_bytes']=12*GIB
        self.assertEqual(self.worker.run_once(admission=admission)['state'],'passed')
        self.assertEqual(self.worker.status()[0]['attempts'],1)
        self.assertEqual(self.marker.read_text(),'ok')

    def test_probe_exception_does_not_launch(self):
        def bad_probe():
            raise RuntimeError('sensor failure')
        result=self.worker.run_once(admission=lambda:admission_for_build(probe=bad_probe,job_ram_gib=2))
        self.assertEqual(result['state'],'deferred')
        self.assertFalse(self.marker.exists())
        self.assertIn('Admission probe failed',result['error'])

    def test_no_admission_keeps_backward_compatibility(self):
        self.assertEqual(self.worker.run_once()['state'],'passed')
