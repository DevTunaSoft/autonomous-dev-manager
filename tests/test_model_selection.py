import unittest
from adm.model_selection import select_installed_model
from adm.engine import SafetyError

class ModelSelectionTests(unittest.TestCase):
    def test_16gb_chooses_small_coding_model(self):
        x = select_installed_model(['qwen2.5-coder:3b', 'qwen2.5-coder:7b'], ram_gib=16)
        self.assertEqual(x['model'], 'ollama/qwen2.5-coder:3b')
        self.assertFalse(x['inference_verified'])
    def test_32gb_chooses_larger_model(self):
        x = select_installed_model(['qwen2.5-coder:3b', 'qwen2.5-coder:7b'], ram_gib=32)
        self.assertEqual(x['model'], 'ollama/qwen2.5-coder:7b')
    def test_does_not_assume_unknown_size(self):
        with self.assertRaises(SafetyError):
            select_installed_model(['qwen2.5-coder:latest'], ram_gib=32)
    def test_does_not_choose_non_coding_model(self):
        with self.assertRaises(SafetyError):
            select_installed_model(['llama3:3b'], ram_gib=16)
    def test_explicit_preference_must_fit_and_exist(self):
        with self.assertRaises(SafetyError):
            select_installed_model(['qwen2.5-coder:7b'], ram_gib=16, preferred='ollama/qwen2.5-coder:7b')
        x = select_installed_model(['qwen2.5-coder:3b'], ram_gib=16, preferred='ollama/qwen2.5-coder:3b')
        self.assertEqual(x['model'], 'ollama/qwen2.5-coder:3b')
    def test_malicious_names_ignored(self):
        with self.assertRaises(SafetyError):
            select_installed_model(['qwen2.5-coder:3b;rm -rf /'], ram_gib=16)
    def test_invalid_ram(self):
        for ram in [0, -1, float('nan'), 10000]:
            with self.subTest(ram=ram), self.assertRaises(SafetyError):
                select_installed_model([], ram_gib=ram)
