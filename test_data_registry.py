import csv
import unittest
from pathlib import Path

ROOT = Path(__file__).parent

class TestDataRegistry(unittest.TestCase):
    def test_all_model_families_have_a_source_record(self):
        with open(ROOT / 'data_source_registry.csv', newline='', encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f, delimiter=';'))
        self.assertEqual(len(rows), 14)
        self.assertEqual({r['model'] for r in rows}, {f'M{i:02d}' for i in range(1, 15)})
        self.assertTrue(all(r['provider'] and r['url'] and r['limitations'] for r in rows))

    def test_all_model_families_have_an_empirical_test(self):
        with open(ROOT / 'empirical_test_matrix.csv', newline='', encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f, delimiter=';'))
        self.assertEqual(len(rows), 14)
        self.assertEqual({r['model'] for r in rows}, {f'M{i:02d}' for i in range(1, 15)})
        self.assertTrue(all(r['primary_test'] for r in rows))

if __name__ == '__main__':
    unittest.main()
