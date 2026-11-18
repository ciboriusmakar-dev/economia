import gzip, json, subprocess, sys, tempfile, unittest
from pathlib import Path
T = Path(__file__).parent / 'eurostat_tsv_tools.py'
SAMPLE = "freq,unit,geo\\TIME_PERIOD\t2007 \t2008 \t2009 \nA,X,DE\t: \t1.5 b\t0 \nA,X,FR\t2 \t3 \t4 \n"


class Tools(unittest.TestCase):
    def run_tool(self, *args):
        return subprocess.run([sys.executable, '-I', str(T), *args], check=True, capture_output=True, text=True)

    def test_filter_and_long(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); src = d / 's.tsv.gz'
            src.write_bytes(gzip.compress(SAMPLE.encode()))
            self.run_tool('filter', str(src), '--geo', 'DE', '--out', str(d / 'f.tsv'))
            self.assertEqual(len((d / 'f.tsv').read_text().splitlines()), 2)
            self.run_tool('long', str(d / 'f.tsv'), '--geo', 'DE', '--from', '2008', '--out', str(d / 'l.csv'))
            rows = (d / 'l.csv').read_text().splitlines()
            self.assertEqual(rows[0], 'freq,unit,geo,period,value,flag')
            self.assertEqual(rows[1:], ['A,X,DE,2008,1.5,b', 'A,X,DE,2009,0,'])   # ':' пропущен, ноль сохранён
            prov = json.loads((d / 'f.tsv.provenance.json').read_text())
            self.assertEqual(len(prov['source_sha256']), 64)


if __name__ == '__main__':
    unittest.main()
