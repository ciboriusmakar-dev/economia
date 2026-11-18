import csv, json, tempfile, unittest, zipfile
from pathlib import Path
from openpyxl import Workbook
from economia_ingest import ingest_path, read_table, IntakeError
from economia_quality import audit_table, compare_sources
from independent_validation import compare_to_reference

class DataIntakeTests(unittest.TestCase):
 def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
 def tearDown(self): self.tmp.cleanup()
 def test_csv_and_tsv(self):
  for name,sep in [('a.csv',','),('b.tsv','\t')]:
   p=self.root/name; p.write_text('year'+sep+'value\n2020'+sep+'1.2\n2021'+sep+'2.3\n',encoding='utf-8')
   rows,headers,_=read_table(p); self.assertEqual(len(rows),2); self.assertEqual(headers,['year','value'])
 def test_xlsx(self):
  p=self.root/'x.xlsx'; w=Workbook(); s=w.active; s.append(['year','value']); s.append([2020,3]); s.append([2021,4]); w.save(p)
  rows,headers,meta=read_table(p); self.assertEqual(len(rows),2); self.assertEqual(meta['sheet'],'Sheet')
 def test_jsonstat(self):
  p=self.root/'x.json'; p.write_text(json.dumps({'version':'2.0','class':'dataset','id':['geo','time'],'size':[1,2],'dimension':{'geo':{'category':{'index':{'DE':0},'label':{'DE':'Germany'}}},'time':{'category':{'index':{'2020':0,'2021':1},'label':{'2020':'2020','2021':'2021'}}}},'value':[1,None]}),encoding='utf-8')
  rows,headers,meta=read_table(p); self.assertEqual(len(rows),1); self.assertEqual(meta['missing_cells'],1)


 def test_dataset_passport_validation(self):
  src=self.root/'data'; src.mkdir(); (src/'x.csv').write_text('year,value\n2020,1\n',encoding='utf-8')
  passport={'dataset_id':'id1','source_id':'source1','version':'1','retrieved_at':'2026-11-15','licence_id':'CC-BY-4.0','attribution':'source attribution','files':['x.csv'],'data_mode':'real','origin':'observed'}
  (src/'dataset_manifest.json').write_text(json.dumps(passport),encoding='utf-8')
  m=ingest_path(src,self.root/'passport-out'); self.assertEqual(m['records'][0]['passport_audit']['status'],'PASS')

 def test_directory_batch_ingestion(self):
  src=self.root/'tables'; src.mkdir(); (src/'a.csv').write_text('year,value\n2020,1\n',encoding='utf-8'); (src/'b.tsv').write_text('year\tvalue\n2021\t2\n',encoding='utf-8')
  m=ingest_path(src,self.root/'batch'); self.assertEqual(m['ingested_files'],2); self.assertEqual(m['failed_files'],0)

 def test_zip_ingestion_and_original_preserved(self):
  z=self.root/'pack.zip';
  with zipfile.ZipFile(z,'w') as f: f.writestr('folder/a.csv','year,value\n2020,1\n')
  m=ingest_path(z,self.root/'out'); self.assertEqual(m['ingested_files'],1); self.assertTrue((self.root/'out/raw/pack/folder/a.csv').exists())
 def test_zip_path_traversal_rejected(self):
  z=self.root/'bad.zip'
  with zipfile.ZipFile(z,'w') as f: f.writestr('../escape.csv','a\n1\n')
  m=ingest_path(z,self.root/'out'); self.assertEqual(m['failed_files'],1); self.assertFalse((self.root/'escape.csv').exists())
 def test_duplicate_key_and_missing_period(self):
  rows=[{'year':'2020','id':'x','value':'1'},{'year':'2020','id':'x','value':'2'},{'year':'2022','id':'y','value':'3'}]
  a=audit_table(rows,['year','id','value'],key_columns=['year','id'])
  self.assertTrue(any('Дубли ключей' in x for x in a['issues'])); self.assertEqual(a['periods']['gaps'],['2021'])
 def test_unknown_unit_classification_warn(self):
  a=audit_table([{'period':'2020','value':'1'}],['period','value'])
  self.assertTrue(any('Единицы' in x for x in a['warnings'])); self.assertTrue(any('Классификация' in x for x in a['warnings']))
 def test_cross_source_value_conflict(self):
  r=compare_sources([{'source_id':'A','metadata':{'unit':'EUR'},'rows':[{'year':'2020','v':10}]},{'source_id':'B','metadata':{'unit':'EUR'},'rows':[{'year':'2020','v':12}]}],['year'],'v',tolerance_abs=0.1)
  self.assertEqual(r['status'],'FAIL'); self.assertEqual(r['conflict_count'],1)
 def test_cross_source_metadata_mismatch(self):
  r=compare_sources([{'source_id':'A','metadata':{'unit':'EUR'},'rows':[{'year':'2020','v':10}]},{'source_id':'B','metadata':{'unit':'USD'},'rows':[{'year':'2020','v':10}]}],['year'],'v')
  self.assertEqual(r['conflicts'][0]['type'],'METADATA_MISMATCH')
 def test_independent_reference_pass(self):
  p=[{'year':'2020','value':'10'}]; r=[{'year':'2020','value':'10.01','unit':'EUR','reference_source':'official'}]
  out=compare_to_reference(p,r,['year'],abs_tolerance=.02)
  self.assertEqual(out['status'],'PASS'); self.assertAlmostEqual(out['MAE'],.01)
 def test_independent_reference_not_testable(self):
  out=compare_to_reference([{'year':'2020','value':'1'}],[],['year'])
  self.assertEqual(out['status'],'NOT_TESTABLE')

 def test_reference_must_be_independent(self):
  out=compare_to_reference([{'year':'2020','value':'10','source_id':'official'}],[{'year':'2020','value':'10','unit':'EUR','reference_source':'official'}],['year'])
  self.assertEqual(out['status'],'FAIL'); self.assertEqual(out['errors'][0]['reason'],'reference_is_not_independent_source')
 def test_reference_metadata_mismatch_fails(self):
  out=compare_to_reference([{'year':'2020','value':'10','unit':'USD'}],[{'year':'2020','value':'10','unit':'EUR','reference_source':'official'}],['year'])
  self.assertEqual(out['status'],'FAIL'); self.assertEqual(out['errors'][0]['reason'],'metadata_mismatch')

 def test_missing_reference_fails(self):
  out=compare_to_reference([{'year':'2020','value':'1'}],[{'year':'2021','value':'1','unit':'EUR','reference_source':'x'}],['year'])
  self.assertEqual(out['status'],'FAIL')

 def test_monthly_and_quarterly_gaps(self):
  monthly=audit_table([{'period':'2020-01','value':'1'},{'period':'2020-03','value':'2'}],['period','value'])
  self.assertEqual(monthly['periods']['frequency'],'monthly'); self.assertEqual(monthly['periods']['gaps'],['2020-02'])
  quarterly=audit_table([{'period':'2020-Q1','value':'1'},{'period':'2020-Q3','value':'2'}],['period','value'])
  self.assertEqual(quarterly['periods']['frequency'],'quarterly'); self.assertEqual(quarterly['periods']['gaps'],['2020-Q2'])
 def test_cross_source_classification_mismatch(self):
  r=compare_sources([{'source_id':'A','metadata':{'unit':'EUR','classification':'NACE Rev.2'},'rows':[{'year':'2020','v':10}]},{'source_id':'B','metadata':{'unit':'EUR','classification':'NACE Rev.2.1'},'rows':[{'year':'2020','v':10}]}],['year'],'v')
  self.assertEqual(r['conflicts'][0]['type'],'METADATA_MISMATCH')

 def test_all_14_modules_have_test_contract(self):
  import csv
  p=Path(__file__).with_name('EMPIRICAL_TEST_PLAN_M01_M14_RU.csv')
  with p.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
  self.assertEqual({r['module'] for r in rows},{f'M{i:02}' for i in range(1,15)})
  self.assertTrue(all(r['input_data'] and r['pass_rule'] and r['fail_rule'] for r in rows))

if __name__=='__main__': unittest.main()
