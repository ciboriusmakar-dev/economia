import json, sqlite3, tempfile, unittest
from pathlib import Path
from economia_ingest import ingest_path
from economia_repository import connect, persist_intake

ROOT = Path(__file__).parent

class TestIntakePersistence(unittest.TestCase):
    def test_roundtrip_and_idempotence(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / 'out'
            m = ingest_path(ROOT / 'data' / 'pilot_input', out)
            conn = connect(Path(t) / 'e.sqlite')
            r1 = persist_intake(conn, m, out)
            n = m['ingested_files']
            self.assertGreaterEqual(n, 4)
            self.assertEqual(r1['added'], n)
            self.assertEqual(r1['failed'], 0)
            files = conn.execute('select count(*) from economia_intake_file').fetchone()[0]
            rows = conn.execute('select count(*) from economia_intake_row').fetchone()[0]
            self.assertEqual(files, n)
            self.assertEqual(rows, sum(x['rows'] for x in m['records']))
            r2 = persist_intake(conn, m, out)          # повтор не дублирует
            self.assertEqual(r2['added'], 0)
            self.assertEqual(r2['skipped_duplicates'], n)
            self.assertEqual(conn.execute('select count(*) from economia_intake_row').fetchone()[0], rows)
            # хеш исходника сохранён как в манифесте
            sha = conn.execute('select source_sha256 from economia_intake_file where source_file like "M01%"').fetchone()[0]
            self.assertEqual(sha, next(x['source_sha256'] for x in m['records'] if x['source_file'].startswith('M01')))
            conn.close()

    def test_failed_file_logged(self):
        with tempfile.TemporaryDirectory() as t:
            bad = Path(t) / 'in'; bad.mkdir()
            (bad / 'x.csv').write_text('a,a\n1,2\n', encoding='utf-8')   # повторяющиеся заголовки
            out = Path(t) / 'out'
            m = ingest_path(bad, out)
            conn = connect(Path(t) / 'e.sqlite')
            r = persist_intake(conn, m, out)
            self.assertEqual(r['failed'], 1)
            n = conn.execute("select count(*) from economia_quality_event where code='intake_failed'").fetchone()[0]
            self.assertEqual(n, 1)
            conn.close()

if __name__ == '__main__':
    unittest.main()
