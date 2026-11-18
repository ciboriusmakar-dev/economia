import unittest, tempfile, io
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from eurostat_api import dataset_url, comext_trade_url, BASE_COMEXT, BASE_STATISTICS
from acquire_full_datasets import download_comext_products

class EurostatURLTests(unittest.TestCase):
    def test_ds_prefixed_prodcom_uses_comext_api(self):
        u = dataset_url('ds-059358', {'reporter':'DE'})
        self.assertTrue(u.startswith(BASE_COMEXT))
        self.assertIn('reporter=DE', u)

    def test_standard_dataset_uses_statistics_api(self):
        u = dataset_url('sts_trtu_m', {'geo':'DE'})
        self.assertTrue(u.startswith(BASE_STATISTICS))
        self.assertIn('geo=DE', u)

    def test_comext_trade_request_is_bounded_and_uses_world_partner(self):
        u = comext_trade_url('2523', reporter='DE', partner='WORLD', flow='1', start_year=2008, end_year=2025)
        self.assertTrue(u.startswith(BASE_COMEXT + 'ds-045409?'))
        for token in ('reporter=DE','partner=WORLD','product=2523','flow=1','indicators=QUANTITY_IN_100KG','sinceTimePeriod=2008','untilTimePeriod=2025'):
            self.assertIn(token,u)

    def test_comext_trade_rejects_unfiltered_or_bad_product_code(self):
        with self.assertRaises(ValueError): comext_trade_url('')
        with self.assertRaises(ValueError): comext_trade_url('2523',flow='3')

    def test_comext_downloader_continues_after_missing_indicator(self):
        with tempfile.TemporaryDirectory() as tmp:
            codes=Path(tmp)/'codes.txt';codes.write_text('2523\n25231000\n',encoding='utf-8')
            calls=[]
            def fake_download(name,url,timeout=120):
                calls.append(name)
                if 'supplementary_quantity' in name:
                    raise RuntimeError('no supplementary quantity for this product')
                return {'name':name,'status':'downloaded'}
            with patch('acquire_full_datasets.download',side_effect=fake_download):
                with redirect_stdout(io.StringIO()): results=download_comext_products(codes)
            self.assertEqual(len(calls),12)
            self.assertEqual(sum(x.get('status')=='failed' for x in results),4)
            self.assertEqual(sum(x.get('status')=='downloaded' for x in results),8)

    def test_invalid_dataset_code_rejected(self):
        with self.assertRaises(ValueError):
            dataset_url('../dataset', {})

if __name__ == '__main__':
    unittest.main()
