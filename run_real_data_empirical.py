"""Recompute limited empirical pilot metrics from versioned source extracts."""
from pathlib import Path
import csv, json
import numpy as np
ROOT=Path(__file__).parent
def read_csv(name):
 with (ROOT/"data"/"pilot_input"/name).open(encoding="utf-8",newline="") as f: return list(csv.DictReader(f))
def main():
 m01=read_csv("M01_germany_cement_balance_2021_2025.csv")
 m01_res={r["year"]:round(float(r["production_mt"])+float(r["imports_mt"])-float(r["domestic_consumption_mt"])-float(r["exports_mt"]),6) for r in m01}
 sec=read_csv("M04_M05_germany_business_sectors_2023.csv")
 y=np.log([float(r["gva_factor_cost_eur_mn"]) for r in sec])
 k=np.log([float(r["gross_investment_eur_mn"]) for r in sec])
 l=np.log([float(r["persons_employed"]) for r in sec])
 X=np.column_stack([np.ones(len(sec)),k,l]); b=np.linalg.lstsq(X,y,rcond=None)[0]
 residual=y-X@b; sse=float(residual@residual); sst=float(((y-y.mean())**2).sum())
 m06=read_csv("M06_destatis_supply_use_2023.csv")
 out={"M01":{"n":len(m01),"unallocated_balance_item_mt":m01_res,"residual_recalculation_matches":all(abs((float(r["production_mt"])+float(r["imports_mt"])-float(r["domestic_consumption_mt"])-float(r["exports_mt"]))-float(r["unexplained_balance_item_mt"]))<1e-6 for r in m01)},"M04":{"n":len(sec),"coefficients":{"intercept":float(b[0]),"investment_proxy":float(b[1]),"labour":float(b[2])},"r_squared_in_sample":1-sse/sst,"condition_number":float(np.linalg.cond(X)),"warning":"Exploratory only: investment flow is not capital stock."},"M05":{"n":len(sec),"mean_staff_cost_share_turnover":float(np.mean([float(r["staff_cost_share_turnover"]) for r in sec])),"mean_staff_cost_per_person_eur":float(np.mean([float(r["staff_cost_per_person_eur"]) for r in sec]))},"M06":{"n_product_groups":len(m06),"max_use_identity_abs_difference_eur_bn":max(abs(float(r["use_identity_difference_eur_bn"])) for r in m06),"leontief_coefficients_estimated":False}}
 (ROOT/"real_data_empirical_results_recomputed.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
