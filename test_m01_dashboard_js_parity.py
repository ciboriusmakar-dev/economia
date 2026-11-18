"""Сверка расчёта панели в браузере (JS) с расчётом на Python на контрольном наборе двух стран.
Тест пропускается, если Playwright/Chromium недоступны."""
import json, tempfile, unittest
from pathlib import Path
from m01_dashboard import build_html
from m01_surplus_report import build_report

ROOT = Path(__file__).parent
FIX = ROOT / 'test_fixtures' / 'synthetic_two_countries_TEST_ONLY.csv'
try:
    from playwright.sync_api import sync_playwright
    HAVE = True
except Exception:
    HAVE = False

def key(r): return (r['country'], r['year'], r['product_code'], r['unit'])

@unittest.skipUnless(HAVE, 'Playwright не установлен')
class TestParity(unittest.TestCase):
    def test_js_matches_python(self):
        py = build_report(FIX)
        with tempfile.TemporaryDirectory() as t:
            page_file = Path(t) / 'empty.html'; build_html(None, page_file)
            with sync_playwright() as p:
                try:
                    br = p.chromium.launch()
                except Exception as e:
                    self.skipTest(f'Chromium недоступен: {e}')
                pg = br.new_page(); errors = []
                pg.on('pageerror', lambda e: errors.append(str(e)))
                pg.goto(page_file.as_uri())
                js = pg.evaluate('t => window.__buildFromCsv(t, "x.csv")', FIX.read_text(encoding='utf-8'))
                pg.set_input_files('#file', str(FIX))                    # загрузка файла через интерфейс
                opts = lambda sel: pg.eval_on_selector_all(sel + ' option', 'o=>o.map(x=>x.value)')
                pg.click('[data-t=goods]')                               # товары: страна × год
                for c in opts('#country'):
                    for y in opts('#year'):
                        pg.select_option('#country', c); pg.select_option('#year', y)
                for tab, fields in (('map', ('#product', '#year', '#metric')), ('trend', ('#country', '#product'))):
                    pg.click(f'[data-t={tab}]')
                    for f in fields:
                        for v in opts(f):
                            pg.select_option(f, v)
                self.assertGreater(len(pg.inner_text('#view')), 0)
                br.close()
            self.assertEqual(errors, [])
        a = {key(r): r for r in py['rows']}; c = {key(r): r for r in js['rows']}
        self.assertEqual(set(a), set(c))
        for k in a:
            for f in ('production', 'imports', 'exports', 'apparent_consumption', 'net_exports'):
                self.assertAlmostEqual(a[k][f], c[k][f], places=9, msg=f'{k} {f}')
            self.assertEqual(a[k].get('converges'), c[k].get('converges'), msg=str(k))
            if 'residual' in a[k]: self.assertAlmostEqual(a[k]['residual'], c[k]['residual'], places=9)
        inc_py = {(x['country'], x['year'], x['product_code'], tuple(x['missing_indicators'])) for x in py['incomplete']}
        inc_js = {(x['country'], x['year'], x['product_code'], tuple(x['missing_indicators'])) for x in js['incomplete']}
        self.assertEqual(inc_py, inc_js)

if __name__ == '__main__':
    unittest.main()
