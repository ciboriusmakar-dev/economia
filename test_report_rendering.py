"""Отчёты: у каждого модуля есть «Главное», график, нет «−0,00», nan и None."""
import re, runpy, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent


class ReportRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runpy.run_path(str(ROOT / 'examples' / 'build_demo_reports.py'), run_name='demo')
        cls.files = sorted((ROOT / 'examples' / 'spec_demo').glob('M*_report.html'))

    def test_all_reports(self):
        self.assertEqual(len(self.files), 13)

    def test_content(self):
        for f in self.files:
            h = f.read_text(encoding='utf-8')
            self.assertIn('Главное', h, f.name)
            self.assertIn('<svg', h, f.name)
            self.assertIn('На что обратить внимание', h, f.name)
            body = h.split('<details>')[0]
            self.assertNotIn('−0,00', body, f.name)
            self.assertIsNone(re.search(r'>\s*(nan|None|inf)\s*<', body), f.name)

    def test_markdown_twins(self):
        for f in self.files:
            md = f.with_suffix('.md').read_text(encoding='utf-8')
            self.assertIn('Главное', md, f.name)
            self.assertNotIn('−0,00', md, f.name)


if __name__ == '__main__':
    unittest.main()
