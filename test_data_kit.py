import csv, importlib.util, unittest
from pathlib import Path

ROOT = Path(__file__).parent

class TestDataKit(unittest.TestCase):
    def _items(self):
        spec = importlib.util.spec_from_file_location('fa', ROOT / 'data_kit' / 'fetch_all.py')
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        return m.ITEMS

    def test_registry_matches_fetch_script(self):
        with open(ROOT / 'data_kit_datasets.csv', newline='', encoding='utf-8-sig') as f:
            reg = {r['dataset_id']: r for r in csv.DictReader(f, delimiter=';')}
        for mods, src, ident, url, fname, lic in self._items():
            self.assertIn(ident, reg)
            self.assertEqual(reg[ident]['download_url'], url)

    def test_no_dataset_marked_licence_verified_or_downloaded_without_evidence(self):
        with open(ROOT / 'data_kit_datasets.csv', newline='', encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f, delimiter=';'))
        self.assertTrue(all(r['licence_verified'] == 'NO' for r in rows))
        self.assertTrue(all(r['download_status'] != 'DOWNLOADED' for r in rows))

    def test_filtered_datasets_not_in_bulk_script(self):
        ids = {i[2] for i in self._items()}
        self.assertFalse({'ds-059358', 'ds-059367', 'ds-045409'} & ids)

if __name__ == '__main__':
    unittest.main()
