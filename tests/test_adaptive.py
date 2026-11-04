import unittest
from adm.adaptive import GIB, decide

class AdaptiveTests(unittest.TestCase):
    def snapshot(self, ram, disk=40, cpus=8):
        return {'ram_available_bytes':ram*GIB,'disk_free_bytes':disk*GIB,'cpu_count':cpus}
    def test_16gb_sequential(self):
        d=decide(self.snapshot(7),job_ram_gib=3)
        self.assertTrue(d.allowed)
        self.assertEqual(d.max_parallel_builds,1)
    def test_32gb_parallel(self):
        d=decide(self.snapshot(24),job_ram_gib=5)
        self.assertTrue(d.allowed)
        self.assertGreater(d.max_parallel_builds,1)
    def test_model_unload_requires_remeasurement(self):
        d=decide(self.snapshot(4),job_ram_gib=5,model_loaded_gib=5)
        self.assertFalse(d.allowed)
        self.assertTrue(d.unload_model_first)
    def test_no_memory_cannot_proceed(self):
        self.assertFalse(decide(self.snapshot(2),job_ram_gib=7).allowed)
    def test_low_disk(self):
        self.assertFalse(decide(self.snapshot(20,3),job_ram_gib=2,job_disk_gib=2).allowed)
    def test_unknown_resources_fail_closed(self):
        self.assertFalse(decide({'ram_available_bytes':None,'disk_free_bytes':None},job_ram_gib=1).allowed)
    def test_concurrency_limit(self):
        self.assertFalse(decide(self.snapshot(24),job_ram_gib=2,active_builds=4).allowed)
    def test_invalid_request(self):
        with self.assertRaises(ValueError):decide(self.snapshot(10),job_ram_gib=-1)
