import csv, tempfile, unittest
from pathlib import Path
import numpy as np
from io_matrix_builder import build_and_validate
from m04_m05_models import estimate_m04, estimate_m05
from m02_m03_market_models import m02_iv_equilibrium,m03_elasticity
from m01_prodcom_balance import calculate as m01_calculate

class Stage2Tests(unittest.TestCase):
 def tmp(self):
  d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup);return Path(d.name)
 def write(self,p,header,rows):
  with p.open('w',newline='',encoding='utf-8') as f:w=csv.writer(f);w.writerow(header);w.writerows(rows)
 def test_m01_eurostat_missing_marker_is_not_cast_to_float(self):
  d=self.tmp();p=d/'prodcom.csv'
  self.write(p,['country','year','product_code','indicator','value','unit','flag'],[['DE',2024,'P1','PRODQNT','..','T',''],['DE',2024,'P1','IMPQNT',20,'T',''],['DE',2024,'P1','EXPQNT',30,'T','']])
  r=m01_calculate(p);self.assertEqual(r['incomplete'],1);self.assertIsNone(r['rows'][0]['apparent_consumption'])
 def test_m01_apparent_consumption_preserves_flags(self):
  d=self.tmp();p=d/'prodcom.csv'
  self.write(p,['country','year','product_code','indicator','value','unit','flag'],[
   ['DE',2024,'P1','PRODQNT',100,'T',''],['DE',2024,'P1','IMPQNT',20,'T','E'],['DE',2024,'P1','EXPQNT',30,'T','']])
  r=m01_calculate(p);self.assertEqual(r['rows'][0]['apparent_consumption'],90);self.assertEqual(r['rows'][0]['source_flags']['IMPQNT'],'E')
 def test_m06_full_matrix_identity(self):
  d=self.tmp();self.write(d/'Z.csv',['industry_id','A','B'],[['A',2,1],['B',1,2]])
  self.write(d/'x.csv',['industry_id','gross_output'],[['A',10],['B',10]])
  # A=[[.2,.1],[.1,.2]], x=[10,10], y=(I-A)x=[7,7]
  self.write(d/'Y.csv',['industry_id','domestic_final_demand'],[['A',7],['B',7]])
  A,r=build_and_validate(d/'Z.csv',d/'x.csv',d/'Y.csv')
  self.assertTrue(np.allclose(A,[[.2,.1],[.1,.2]]));self.assertLess(r['observed_output_reconstruction_max_relative_error'],1e-10)
 def test_m06_reject_order_mismatch(self):
  d=self.tmp();self.write(d/'Z.csv',['industry_id','A','B'],[['B',1,2],['A',2,1]])
  self.write(d/'x.csv',['industry_id','gross_output'],[['A',10],['B',10]])
  self.write(d/'Y.csv',['industry_id','domestic_final_demand'],[['A',7],['B',7]])
  with self.assertRaises(ValueError):build_and_validate(d/'Z.csv',d/'x.csv',d/'Y.csv')
 def test_m04_cluster_covariance_rejects_single_cluster(self):
  from m04_m05_models import _ols_cluster
  X=np.column_stack([np.ones(8),np.arange(8,dtype=float)]);y=np.arange(8,dtype=float)**2
  with self.assertRaisesRegex(ValueError,'не менее двух'):_ols_cluster(X,y,['one']*8)
 def test_m04_capital_stock_and_labour_panel(self):
  d=self.tmp();p=d/'stan.csv';rows=[]
  for i in range(8):
   ind=f'I{i}'
   for t,yr in enumerate(range(2000,2012)):
    K=100+i*13+t*2.7+8*np.sin((i+1)*(t+1)/4)
    L=55+i*4.2+t*1.4+5*np.cos((i+2)*(t+1)/5)
    VA=(1+0.04*i)*(K**.35)*(L**.65)
    rows.append(['DE',ind,yr,'VA',VA,'']);rows.append(['DE',ind,yr,'K_STOCK',K,'']);rows.append(['DE',ind,yr,'LABOUR',L,''])
  with p.open('w',newline='') as f:w=csv.writer(f);w.writerow(['country','industry','year','variable','value','flag']);w.writerows(rows)
  r=estimate_m04(p,min_obs=20);self.assertEqual(r['n'],96);self.assertTrue(np.isfinite(r['capital_elasticity']))
 def test_m05_large_reconciliation_residual_fails(self):
  d=self.tmp();p=d/'cost.csv';self.write(p,['industry','year','output','intermediate_consumption','compensation','fixed_capital_consumption','net_operating_surplus','other_taxes'],[['A',2020,100,60,20,5,5,0]])
  r=estimate_m05(p);self.assertEqual(r['status'],'FAIL_COST_RECONCILIATION');self.assertAlmostEqual(r['max_relative_abs_reconciliation_residual'],.1)
 def test_m05_cost_reconciliation(self):
  d=self.tmp();p=d/'cost.csv';self.write(p,['industry','year','output','intermediate_consumption','compensation','fixed_capital_consumption','net_operating_surplus','other_taxes'],[['A',2020,100,60,20,5,12,3]])
  r=estimate_m05(p);self.assertEqual(r['max_abs_reconciliation_residual'],0)
 def test_m03_elasticity(self):
  d=self.tmp();p=d/'market.csv';rows=[]
  for i in range(60):
   price=100+i*.2;qty=300*(price/100)**-.6
   rows.append([f'{2000+i//12}-{i%12+1:02d}',price,qty,1,1])
  self.write(p,['period','price_index','quantity_index','demand_shifter','supply_shifter'],rows)
  r=m03_elasticity(p);self.assertAlmostEqual(r['log_price_coefficient'],-.6,places=4)
 def test_m02_iv_pipeline(self):
  d=self.tmp();p=d/'market.csv';rows=[]
  for i in range(100):
   zd=1+0.01*i+0.1*np.sin(i);zs=1+0.02*i+0.1*np.cos(i);price=100*np.exp(.1*np.sin(i)+.05*np.cos(i));qty=200*(price/100)**-.5*np.exp(.2*np.log(zd))
   rows.append([f'{2000+i//12}-{i%12+1:02d}',price,qty,zd,zs])
  self.write(p,['period','price_index','quantity_index','demand_shifter','supply_shifter'],rows)
  r=m02_iv_equilibrium(p);self.assertEqual(r['n_months'],100)
  self.assertIn('first_stage_excluded_instrument_F_demand',r);self.assertIn('first_stage_excluded_instrument_F_supply',r)
  self.assertIn('demand_price_slope_hac_se',r);self.assertIn('supply_price_slope_hac_se',r)
  self.assertTrue(np.isfinite(r['demand_price_slope_hac_se']));self.assertTrue(np.isfinite(r['supply_price_slope_hac_se']))
if __name__=='__main__':unittest.main(verbosity=2)
