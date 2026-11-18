"""Ежедневное обновление: загрузка, 304, тот же SHA, плохой ответ не затирает хорошую копию."""
import gzip, json, os, subprocess, sys, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
ROOT = Path(__file__).parent
GOOD = gzip.compress(b"freq,unit,geo\\TIME_PERIOD\t2008 \t2009 \nA,X,DE\t1 \t2 \n")
STATE = {'body': GOOD, 'etag': '"v1"'}


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('If-None-Match') == STATE['etag']:
            self.send_response(304); self.end_headers(); return
        self.send_response(200); self.send_header('ETag', STATE['etag']); self.end_headers(); self.wfile.write(STATE['body'])

    def log_message(self, *a): pass


class UpdateData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(('127.0.0.1', 0), H); threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.srv.server_port}/{{id}}'

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def run_update(self, d):
        cfg = Path(d) / 'cfg.json'
        cfg.write_text(json.dumps({'base_url': 'x', 'datasets': [{'id': 't1', 'title': 'T', 'modules': []}]}))
        env = dict(os.environ, ECONOMIA_BASE_URL=self.url)
        r = subprocess.run([sys.executable, str(ROOT / 'update_data.py'), '--raw', f'{d}/raw', '--manifest', f'{d}/man.json', '--config', str(cfg)], env=env, capture_output=True, text=True)
        return r.returncode, json.loads((Path(d) / 'man.json').read_text())['datasets']['t1']

    def test_cycle(self):
        with tempfile.TemporaryDirectory() as d:
            STATE.update(body=GOOD, etag='"v1"')
            rc, m = self.run_update(d); self.assertEqual((rc, m['status']), (0, 'обновлён')); sha1 = m['sha256']
            rc, m = self.run_update(d); self.assertEqual(rc, 0); self.assertIn('304', m['status'])
            STATE.update(body=b'<html>error</html>', etag='"v2"')           # плохой ответ
            rc, m = self.run_update(d); self.assertEqual(rc, 0); self.assertIn('прежняя копия', m['status']); self.assertEqual(m['sha256'], sha1)
            new = gzip.compress(b"freq,unit,geo\\TIME_PERIOD\t2008 \t2009 \nA,X,DE\t1 \t3 \n")
            STATE.update(body=new, etag='"v3"')
            rc, m = self.run_update(d); self.assertEqual(m['status'], 'обновлён'); self.assertNotEqual(m['sha256'], sha1); self.assertEqual(len(m['history']), 2)

    def test_first_download_bad_fails(self):
        with tempfile.TemporaryDirectory() as d:
            STATE.update(body=b'junk', etag='"z"')
            rc, m = self.run_update(d); self.assertEqual(rc, 1); self.assertIn('ОШИБКА', m['status'])


class WorldBank(unittest.TestCase):
    def test_wb_json_valid_and_bad(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('ud', ROOT / 'update_data.py'); ud = importlib.util.module_from_spec(spec); spec.loader.exec_module(ud)
        with tempfile.TemporaryDirectory() as d:
            ok, bad, ok_part = Path(d) / 'a.json', Path(d) / 'b.json', Path(d) / 'a.json.part'
            ok.write_text(json.dumps([{'page': 1}, [{'date': '2020', 'value': 1.0}]]))
            ok_part.write_text(ok.read_text())
            bad.write_text(json.dumps([{'message': [{'id': '120'}]}]))
            self.assertTrue(ud.valid(str(ok))); self.assertTrue(ud.valid(str(ok_part))); self.assertFalse(ud.valid(str(bad)))


class SiteModes(unittest.TestCase):
    def test_report_has_mode_toggle(self):
        from economia_report import to_html
        h = to_html({'model_id': 'M07', 'status': 'COMPLETED', 'mode': 'real', 'outputs': {'summary_ru': ['x']}, 'warnings': [], 'errors': []})
        self.assertIn('data-m="pro"', h); self.assertIn('Для профессионала', h); self.assertIn('economia_mode', h)


if __name__ == '__main__':
    unittest.main()
