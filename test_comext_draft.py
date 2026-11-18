import csv, re, unittest
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).parent

class TestComextDraft(unittest.TestCase):
    def test_draft_structure(self):
        with open(ROOT / 'data_kit' / 'comext_requests_draft.csv', newline='', encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f, delimiter=';'))
        self.assertEqual(len(rows), 80)
        self.assertEqual({r['reporter'] for r in rows}, {'DE', 'FR'})
        self.assertTrue(all(r['status'] == 'DRAFT_NOT_VERIFIED' for r in rows))
        for r in rows:
            q = parse_qs(urlparse(r['url']).query)
            self.assertEqual(q['product'], [r['hs_code']])
            self.assertEqual(q['reporter'], [r['reporter']])
            self.assertEqual(q['flow'], ['1' if r['flow'] == 'import' else '2'])
            self.assertTrue(re.fullmatch(r'\d{4}', r['hs_code']))
        self.assertEqual(len({r['url'] for r in rows}), 80)   # без дублей

if __name__ == '__main__':
    unittest.main()
