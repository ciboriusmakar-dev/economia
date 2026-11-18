import csv, tempfile, unittest
from pathlib import Path
from m01_surplus_report import build_report, to_markdown

ROOT = Path(__file__).parent

def write(rows):
    t = tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False, newline='', encoding='utf-8')
    w = csv.writer(t); w.writerow(['country', 'year', 'product_code', 'indicator', 'value', 'unit', 'flag'])
    w.writerows(rows); t.close(); return t.name

class TestSurplusReport(unittest.TestCase):
    def test_pilot_cement(self):
        rep = build_report(ROOT / 'data' / 'pilot_input' / 'M01_cement_DE_canonical.csv')
        self.assertEqual(rep['n_rows'], 5)
        self.assertTrue(all(r['identity_check'] for r in rep['rows']))
        self.assertTrue(all(r['position'].startswith('избыток') for r in rep['rows']))
        self.assertAlmostEqual(rep['rows'][0]['residual'], 0.166, places=6)   # = неучтённая статья баланса из источника
        self.assertEqual(rep['convergence']['checked'], 5)

    def test_surplus_deficit_and_missing_not_zero_filled(self):
        rows = []
        for c, p, i, e in [('AA', 10, 1, 4), ('BB', 2, 7, 1)]:
            for ind, v in (('PRODQNT', p), ('IMPQNT', i), ('EXPQNT', e)): rows.append([c, 2024, 'X', ind, v, 'T', ''])
        rows += [['CC', 2024, 'X', 'PRODQNT', 5, 'T', ''], ['CC', 2024, 'X', 'IMPQNT', ':', 'T', ':'], ['CC', 2024, 'X', 'EXPQNT', 1, 'T', '']]
        rep = build_report(write(rows))
        pos = {r['country']: r['position'] for r in rep['rows']}
        self.assertTrue(pos['AA'].startswith('избыток')); self.assertTrue(pos['BB'].startswith('дефицит'))
        self.assertEqual(rep['n_incomplete'], 1); self.assertEqual(rep['incomplete'][0]['country'], 'CC')
        self.assertNotIn('CC', pos)
        self.assertIn('нет IMPQNT', to_markdown(rep))

    def test_perfect_convergence(self):
        rows = [['AA', 2024, 'X', i, v, 'T', ''] for i, v in (('PRODQNT', 10), ('IMPQNT', 1), ('EXPQNT', 4), ('CONSQNT', 7))]
        rep = build_report(write(rows))
        self.assertTrue(rep['rows'][0]['converges']); self.assertEqual(rep['convergence']['converging'], 1)

if __name__ == '__main__':
    unittest.main()
