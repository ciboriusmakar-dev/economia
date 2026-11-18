import json, re, tempfile, unittest
from pathlib import Path
from m01_dashboard import build_html

ROOT = Path(__file__).parent

class TestDashboard(unittest.TestCase):
    def test_builds_self_contained_html_with_data(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / 'd.html'
            rep = build_html(ROOT / 'data' / 'pilot_input' / 'M01_cement_DE_canonical.csv', out)
            html = out.read_text(encoding='utf-8')
            self.assertIn('<title>M01', html)
            self.assertNotIn('http://', html.replace('http://www.w3.org', ''))   # без внешних ресурсов
            self.assertNotIn('src="http', html)
            m = re.search(r'load\((\{.*\})\);\n</script>', html, re.S)
            data = json.loads(m.group(1).replace('<\\/', '</'))
            self.assertEqual(len(data['rows']), rep['n_rows'])
            self.assertEqual(data['rows'][0]['country'], 'DE')

    def test_incomplete_rows_embedded_not_as_rows(self):
        import csv
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'in.csv'
            with open(p, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f); w.writerow(['country', 'year', 'product_code', 'indicator', 'value', 'unit', 'flag'])
                w.writerows([['AA', 2024, 'X', 'PRODQNT', 5, 'T', ''], ['AA', 2024, 'X', 'IMPQNT', ':', 'T', ':'], ['AA', 2024, 'X', 'EXPQNT', 1, 'T', '']])
            rep = build_html(p, Path(t) / 'o.html')
            self.assertEqual(rep['n_rows'], 0); self.assertEqual(rep['n_incomplete'], 1)

if __name__ == '__main__':
    unittest.main()
