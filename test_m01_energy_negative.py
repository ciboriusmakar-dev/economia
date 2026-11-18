import csv, tempfile, unittest
from pathlib import Path
from m01_surplus_report import build_report


class NegativeReportedConsumption(unittest.TestCase):
    def test_negative_reported_is_not_error_and_not_checked(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'x.csv'
            with open(p, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f); w.writerow(['country', 'year', 'product_code', 'indicator', 'value', 'unit', 'flag'])
                for i, v in (('PRODQNT', 0), ('IMPQNT', 5), ('EXPQNT', 9), ('CONSQNT', -3)): w.writerow(['AA', 2024, 'E', i, v, 'TJ', ''])
            r = build_report(str(p))['rows'][0]
            self.assertEqual(r['apparent_consumption'], -4)
            self.assertIsNone(r['converges'])


if __name__ == '__main__':
    unittest.main()
