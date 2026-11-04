import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from adm.queued_ai import enqueue_repair, physical_ram_gib
from adm.worker import WorkerSupervisor
from adm.engine import SafetyError

class AutoQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.root=self.base/'project'; self.root.mkdir()
        (self.root/'requirements.json').write_text('{"goal":"test"}')
        (self.root/'app.py').write_text('x=1')
        (self.root/'test_app.py').write_text('import unittest')
    def queue(self, **kwargs):
        return enqueue_repair(self.base/'state',self.root,self.base/'evidence',model='auto',**kwargs)
    def test_selects_3b_on_16gb_and_persists_model(self):
        result=self.queue(ram_gib=16,installed_models=['qwen2.5-coder:3b','qwen2.5-coder:7b'])
        self.assertEqual(result['model'],'ollama/qwen2.5-coder:3b')
        self.assertFalse(result['inference_verified'])
        w=WorkerSupervisor(self.base/'state')
        try:
            argv=json.loads(w.db.execute('select argv from jobs where id=?',(result['job_id'],)).fetchone()[0])
            self.assertEqual(argv[argv.index('--model')+1],result['model'])
        finally:w.close()
    def test_selects_7b_on_32gb(self):
        self.assertEqual(self.queue(ram_gib=32,installed_models=['qwen2.5-coder:3b','qwen2.5-coder:7b'])['model'],'ollama/qwen2.5-coder:7b')
    def test_no_eligible_model_fails_without_queue(self):
        with self.assertRaises(SafetyError): self.queue(ram_gib=16,installed_models=['qwen2.5-coder:7b'])
        self.assertFalse((self.base/'state'/'workers.sqlite3').exists())
    def test_live_inventory_used_only_in_auto_mode(self):
        with patch('adm.queued_ai.inspect_ollama',return_value={'installed_models':['qwen2.5-coder:3b']}) as probe:
            self.queue(ram_gib=16)
            probe.assert_called_once()
    def test_explicit_model_does_not_probe(self):
        with patch('adm.queued_ai.inspect_ollama',side_effect=AssertionError('unexpected probe')):
            result=enqueue_repair(self.base/'state',self.root,self.base/'evidence',model='ollama/qwen2.5-coder:3b')
            self.assertEqual(result['model'],'ollama/qwen2.5-coder:3b')
    def test_untrusted_model_name_rejected(self):
        with self.assertRaises(SafetyError): self.queue(ram_gib=32,installed_models=['bad/model:7b'])
    def test_physical_ram_is_positive(self):
        self.assertGreater(physical_ram_gib(),0)
