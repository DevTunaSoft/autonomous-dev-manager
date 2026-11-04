import io
import json
import unittest
from urllib.error import URLError
from adm.model_probe import installed_models, smoke_test, benchmark_report

MODEL='qwen2.5-coder:1.5b'

class Response:
    def __init__(self, payload): self.data=io.BytesIO(json.dumps(payload).encode())
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, n=-1): return self.data.read(n)

class ProbeTests(unittest.TestCase):
    def opener(self, answer='READY', models=None):
        def call(req, timeout):
            self.assertEqual(req.full_url.split('/api/')[0], 'http://127.0.0.1:11434')
            if req.full_url.endswith('/tags'):
                return Response({'models':[{'name':x} for x in (models if models is not None else [MODEL])]})
            payload=json.loads(req.data)
            self.assertEqual(payload['stream'],False)
            self.assertEqual(payload['keep_alive'],'0s')
            return Response({'response':answer,'done':True})
        return call
    def test_installed(self): self.assertEqual(installed_models(opener=self.opener()),[MODEL])
    def test_success(self): self.assertEqual(smoke_test(MODEL,opener=self.opener()).status,'passed')
    def test_bad_answer(self): self.assertEqual(smoke_test(MODEL,opener=self.opener('NOT READY')).status,'failed')
    def test_missing(self): self.assertEqual(smoke_test(MODEL,opener=self.opener(models=[])).status,'missing')
    def test_unfinished(self):
        def op(req,timeout):
            return Response({'models':[{'name':MODEL}]}) if req.full_url.endswith('/tags') else Response({'done':False})
        self.assertEqual(smoke_test(MODEL,opener=op).status,'inconclusive')
    def test_connection_error(self):
        def op(req,timeout): raise URLError('unavailable')
        self.assertEqual(smoke_test(MODEL,opener=op).status,'blocked')
    def test_unknown_model_rejected(self):
        with self.assertRaises(ValueError): smoke_test('untrusted:model',opener=self.opener())
    def test_bad_timeout(self):
        with self.assertRaises(ValueError): installed_models(timeout=0,opener=self.opener())
    def test_duplicate_models(self):
        with self.assertRaises(ValueError): benchmark_report([MODEL,MODEL],opener=self.opener())
    def test_report_not_claiming_coding(self):
        report=benchmark_report([MODEL],opener=self.opener())
        self.assertFalse(report['coding_capability_verified'])
        self.assertEqual(report['results'][0]['status'],'passed')

if __name__=='__main__': unittest.main()
