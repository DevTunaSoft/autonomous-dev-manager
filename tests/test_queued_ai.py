import json
from pathlib import Path
import tempfile
import unittest
from adm.queued_ai import enqueue_repair
from adm.daemon import serve
from adm.worker import WorkerSupervisor
from adm.engine import SafetyError

class QueuedAITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root, self.state, self.evidence = base/'project', base/'state', base/'evidence'
        self.root.mkdir()
        (self.root/'requirements.json').write_text('{"goal":"add numbers"}')
        (self.root/'app.py').write_text('def add(a,b): return a-b\n')
        (self.root/'test_app.py').write_text('import unittest\nfrom app import add\nclass T(unittest.TestCase):\n def test_add(self): self.assertEqual(add(2,3),5)\n')

    def test_queue_is_durable_and_non_replaying(self):
        item = enqueue_repair(self.state, self.root, self.evidence)
        w = WorkerSupervisor(self.state)
        try:
            row = w.db.execute('select argv,max_attempts,state from jobs where id=?',(item['job_id'],)).fetchone()
            argv = json.loads(row[0])
            self.assertEqual(row[1:], (1, 'pending'))
            self.assertIn('adm.ollama_cli', argv[3])
            self.assertEqual(argv[argv.index('--evidence')+1], item['evidence'])
        finally: w.close()

    def test_two_jobs_have_separate_evidence(self):
        a=enqueue_repair(self.state,self.root,self.evidence)
        b=enqueue_repair(self.state,self.root,self.evidence)
        self.assertNotEqual(a['evidence'],b['evidence'])

    def test_invalid_model_rejected(self):
        with self.assertRaises(SafetyError):
            enqueue_repair(self.state,self.root,self.evidence,model='paid/provider')

    def test_invalid_layout_rejected(self):
        with self.assertRaises(SafetyError):
            enqueue_repair(self.root,self.root,self.evidence)

    def test_daemon_executes_queued_ai_and_records_real_failure(self):
        # No Ollama server here: prove the daemon invokes the actual adapter,
        # captures its failure, and does not claim a successful repair.
        item=enqueue_repair(self.state,self.root,self.evidence)
        serve(self.state,poll_interval=.05,job_timeout=15,max_cycles=1)
        w=WorkerSupervisor(self.state)
        try:
            status=w.status()[0]
            self.assertEqual(status['id'],item['job_id'])
            self.assertEqual(status['state'],'failed')
            self.assertEqual(status['attempts'],1)
            report=Path(item['evidence'])/'ollama-direct-report.json'
            self.assertTrue(report.is_file())
            self.assertNotEqual(json.loads(report.read_text())['status'],'verified_direct_repair')
        finally:w.close()

if __name__=='__main__': unittest.main()
