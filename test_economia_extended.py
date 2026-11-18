import unittest, numpy as np, tempfile, sqlite3
from economia_extended_models import *
from economia_engine import execute_model,validate_dataset
from economia_modules import run_model,model_catalog
from economia_quality import audit_csv,audit_dataset_manifest
from economia_repository import connect,register_dataset
from pathlib import Path

class ExtendedModelTests(unittest.TestCase):
 def test_m07_exact_linear(self):
  r=m07_regression([{'x':i,'y':2+3*i} for i in range(10)])
  self.assertAlmostEqual(r['coefficients'][0],2);self.assertAlmostEqual(r['coefficients'][1],3)
 def test_m07_rejects_collinear(self):
  with self.assertRaises(ValueError):m07_regression([{'x':i,'z':2*i,'y':i} for i in range(10)],x=('x','z'))
 def test_m08_did(self):
  rows=[]
  for t,p,ys in [(0,0,[1,1]),(0,1,[2,2]),(1,0,[3,3]),(1,1,[6,6])]:
   for y in ys:rows.append({'treated':t,'post':p,'outcome':y})
  r=m08_difference_in_differences(rows);self.assertEqual(r['did_effect'],2)
 def test_m08_requires_four_cells(self):
  with self.assertRaises(ValueError):m08_difference_in_differences([{'treated':0,'post':0,'outcome':1}])
 def test_m08_warns_about_few_clusters(self):
  rows=[]
  for g in range(4):
   for treated,post in ((0,0),(0,1),(1,0),(1,1)):
    rows.append({'cluster':g,'treated':treated,'post':post,'outcome':2+treated+post+treated*post+g*.1})
  r=m08_difference_in_differences(rows,cluster='cluster')
  self.assertEqual(r['cluster_count'],4);self.assertIn('Мало кластеров',r['warning'])
 def test_m09_backtest(self):
  r=m09_forecast([{'period':f'{i:02d}','value':i} for i in range(10)],horizon=2,min_train=4)
  self.assertEqual(r['forecast'],[10.,11.]);self.assertEqual(r['selected_baseline'],'drift');self.assertEqual(r['backtest_origins'],6)
 def test_m09_seasonal_forecast_alignment(self):
  values=list(range(1,13))*3
  r=m09_forecast([{'period':f'{i:03d}','value':v} for i,v in enumerate(values)],horizon=14,min_train=12,season_length=12)
  self.assertEqual(r['selected_baseline'],'seasonal_naive')
  self.assertEqual(r['forecast'],[1.,2.,3.,4.,5.,6.,7.,8.,9.,10.,11.,12.,1.,2.])
 def test_m10_linear_program(self):
  r=m10_resource_optimisation([{'profit':[3,2],'constraints':{'A_ub':[[1,1],[2,1]],'b_ub':[4,5]}}])
  self.assertTrue(r['optimal']);self.assertAlmostEqual(r['objective_value'],9)
 def test_m11_multi_market(self):
  r=m11_linear_multi_market([{'a':[10,8],'B':[[1,.2],[.1,1]],'c':[2,1],'S':[[1,0],[0,1]]}])
  self.assertLess(r['market_clearing_residual'],1e-10)
 def test_m12_inventory(self):
  r=m12_inventory([{'production':5,'demand':7},{'production':5,'demand':2}],initial_stock=0)
  self.assertEqual(r['total_unmet_demand'],2);self.assertEqual(r['ending_stock'],3)
 def test_m13_max_flow(self):
  r=m13_max_flow([{'edges':[('s','a',3),('s','b',2),('a','t',2),('b','t',3),('a','b',1)]}],source='s',sink='t')
  self.assertAlmostEqual(r['max_flow'],5)
 def test_m14_risk(self):
  r=m14_risk([{'value':x} for x in [1,2,3,4,5]],confidence=.8)
  self.assertEqual(r['quantile'],4);self.assertAlmostEqual(r['expected_shortfall_upper_tail'],5.0)
 def test_unified_contract_real_rejects_synthetic(self):
  ds={'dataset_id':'d','source_id':'s','records':[{'x':1,'y':2}],'origin':'synthetic','data_mode':'real'}
  r=execute_model('M07',m07_regression,ds,mode='real')
  self.assertEqual(r.status,'REJECTED_INPUT')
 def test_unified_m07(self):
  ds={'dataset_id':'d','source_id':'s','records':[{'x':i,'y':1+2*i} for i in range(8)],'origin':'observed','data_mode':'real'}
  r=run_model('M07',ds,{'method':'regression'});self.assertEqual(r['status'],'COMPLETED');self.assertAlmostEqual(r['outputs']['coefficients'][1],2)
 def test_catalog_14(self):self.assertEqual(len(model_catalog()),14)
 def test_quality_audit(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.csv';p.write_text('id,value\n1,2\n1,3\n',encoding='utf-8')
   r=audit_csv(p,key_columns=['id'],required_columns=['id','value'],numeric_columns=['value']);self.assertEqual(r['quality_status'],'FAIL')
 def test_manifest(self):
  self.assertEqual(audit_dataset_manifest({'dataset_id':'d','source_id':'s','version':'1','retrieved_at':'x','licence_id':'l','attribution':'a','files':['f'],'data_mode':'real','origin':'observed'})['status'],'PASS')
 def test_repository_migration(self):
  with tempfile.TemporaryDirectory() as d:
   c=connect(Path(d)/'db.sqlite');self.assertTrue(c.execute("select name from sqlite_master where name='economia_run'").fetchone());c.close()

 def test_m01_unified(self):
  ds={'dataset_id':'d1','source_id':'s1','origin':'observed','data_mode':'real','records':[
   {'country':'DE','year':'2024','product_code':'P1','indicator':'PRODQNT','value':'100','unit':'T','flag':''},
   {'country':'DE','year':'2024','product_code':'P1','indicator':'IMPQNT','value':'20','unit':'T','flag':''},
   {'country':'DE','year':'2024','product_code':'P1','indicator':'EXPQNT','value':'30','unit':'T','flag':''}]}
  r=run_model('M01',ds);self.assertIn(r['status'],{'COMPLETED','COMPLETED_WITH_WARNINGS'});self.assertEqual(r['outputs']['rows'][0]['apparent_consumption'],90)
 def test_m06_unified(self):
  ds={'dataset_id':'d6','source_id':'s6','origin':'observed','data_mode':'real','records':[{'industry_ids':['A','B'],'Z':[[2,1],[1,2]],'gross_output':[10,10],'domestic_final_demand':[7,7]}]}
  r=run_model('M06',ds,{'method':'leontief_basic'});self.assertIn(r['status'],{'COMPLETED','COMPLETED_WITH_WARNINGS'});self.assertLess(r['outputs']['output_reconstruction_max_relative_error'],1e-10)
 def test_m10_infeasible_problem_is_flagged(self):
  r=m10_resource_optimisation([{'profit':[1.0],'constraints':{'A_ub':[[1.0],[-1.0]],'b_ub':[0.0,-1.0]}}])
  self.assertFalse(r['optimal']);self.assertTrue(r['status'].startswith('FAIL_SOLVER_'))
  ds={'dataset_id':'bad-opt','source_id':'fixture','origin':'synthetic','data_mode':'simulation','records':[{'profit':[1.0],'constraints':{'A_ub':[[1.0],[-1.0]],'b_ub':[0.0,-1.0]}}]}
  self.assertEqual(run_model('M10',ds,{'method':'linprog'},mode='simulation')['status'],'FAILED_VALIDATION')
 def test_m10_equality_constraint(self):
  r=m10_resource_optimisation([{'profit':[3,2],'constraints':{'A_ub':[[1,1]],'b_ub':[10],'A_eq':[[1,1]],'b_eq':[4]}}])
  self.assertTrue(r['optimal']);self.assertAlmostEqual(sum(r['decision_variables']),4)
 def test_m14_weighted_tail(self):
  r=m14_risk([{'value':10},{'value':20},{'value':30} ],confidence=.8,weights=[.8,.1,.1])
  self.assertAlmostEqual(r['expected_shortfall_upper_tail'],25)

 def test_m12_lead_time_pipeline(self):
  r=m12_inventory([{'production':0,'demand':1},{'production':0,'demand':1},{'production':0,'demand':1}],initial_stock=0,reorder_point=0,order_quantity=2,lead_time=2)
  self.assertEqual(r['periods'][0]['new_order'],2);self.assertEqual(r['periods'][1]['arrivals'],0);self.assertEqual(r['periods'][2]['arrivals'],2)
 def test_m13_flow_capacity_and_conservation(self):
  r=m13_max_flow([{'edges':[('s','a',4),('a','t',3),('s','t',1)]}],source='s',sink='t')
  self.assertAlmostEqual(r['max_flow'],4)
 def test_repository_registers_14_models(self):
  with tempfile.TemporaryDirectory() as d:
   c=connect(Path(d)/'db.sqlite');from economia_repository import register_modules
   register_modules(c,model_catalog());self.assertEqual(c.execute('select count(*) from economia_module_registry').fetchone()[0],14);c.close()

 def test_unified_m02_m03_m04_m05(self):
  rows=[]
  for i in range(48):
   zd=1+.01*i+.1*np.sin(i);zs=1+.02*i+.1*np.cos(i);price=100*np.exp(.1*np.sin(i)+.05*np.cos(i));qty=200*(price/100)**-.5*np.exp(.2*np.log(zd))
   rows.append({'period':f'{2000+i//12}-{i%12+1:02d}','price_index':price,'quantity_index':qty,'demand_shifter':zd,'supply_shifter':zs})
  for mid in ('M02','M03'):
   out=run_model(mid,{'dataset_id':mid,'source_id':'fixture','origin':'observed','data_mode':'real','records':rows},{'method':{'M02':'iv','M03':'elasticity'}[mid]});self.assertIn(out['status'],{'COMPLETED','COMPLETED_WITH_WARNINGS'},out['errors'])
  panel=[]
  for i in range(5):
   for t in range(8):
    K=100+i*13+t*2.7+8*np.sin((i+1)*(t+1)/4);L=55+i*4.2+t*1.4+5*np.cos((i+2)*(t+1)/5);VA=(1+.04*i)*(K**.35)*(L**.65)
    for var,val in [('VA',VA),('K_STOCK',K),('LABOUR',L)]:panel.append({'country':'DE','industry':f'I{i}','year':2000+t,'variable':var,'value':val,'flag':''})
  out=run_model('M04',{'dataset_id':'M04','source_id':'fixture','origin':'observed','data_mode':'real','records':panel},{'min_obs':30,'method':'production_function'});self.assertEqual(out['status'],'COMPLETED_WITH_WARNINGS',out['errors'])
  costs=[{'industry':'A','year':2020,'output':100,'intermediate_consumption':60,'compensation':20,'fixed_capital_consumption':5,'net_operating_surplus':12,'other_taxes':3}]
  out=run_model('M05',{'dataset_id':'M05','source_id':'fixture','origin':'observed','data_mode':'real','records':costs},{'method':'cost_function'});self.assertEqual(out['status'],'COMPLETED',out['errors'])
  bad_costs=[{'industry':'A','year':2020,'output':100,'intermediate_consumption':60,'compensation':20,'fixed_capital_consumption':5,'net_operating_surplus':5,'other_taxes':0}]
  bad=run_model('M05',{'dataset_id':'M05-bad','source_id':'fixture','origin':'observed','data_mode':'real','records':bad_costs},{'method':'cost_function'});self.assertEqual(bad['status'],'FAILED_VALIDATION')

 def test_report_markdown(self):
  from economia_report import to_markdown
  text=to_markdown({'model_id':'M07','model_version':'1.9.5','status':'COMPLETED','mode':'simulation','inputs_hash':'abc','outputs':{'coef':1},'diagnostics':{},'warnings':[],'errors':[]})
  self.assertIn('не эмпирическое подтверждение',text)
 def test_register_dataset_manifest(self):
  from economia_repository import register_dataset
  with tempfile.TemporaryDirectory() as d:
   c=connect(Path(d)/'db.sqlite');register_dataset(c,{'dataset_id':'d','source_id':'s','version':'1','retrieved_at':'2026-11-15','licence_id':'L','attribution':'A','data_mode':'real','origin':'observed'})
   self.assertEqual(c.execute('select count(*) from economia_dataset_manifest').fetchone()[0],1);c.close()

if __name__=='__main__':unittest.main()
