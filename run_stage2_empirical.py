"""Run all stage-2 empirical pipelines that have their canonical real inputs.
Missing inputs are recorded as BLOCKED, never filled with generated values.
"""
from pathlib import Path
import json
from m01_prodcom_balance import calculate as m01
from m04_m05_models import estimate_m04,estimate_m05
from m02_m03_market_models import m02_iv_equilibrium,m03_elasticity
from io_matrix_builder import build_and_validate
ROOT=Path(__file__).resolve().parent; DATA=ROOT/'data'/'processed'

def run():
    results={}
    tasks={
      'M01':(DATA/'M01_prodcom_long.csv',lambda p:m01(p)),
      'M04':(DATA/'M04_STAN_long.csv',lambda p:estimate_m04(p)),
      'M05':(DATA/'M05_value_added_components.csv',lambda p:estimate_m05(p)),
      'M02':(DATA/'M02_market_monthly.csv',lambda p:m02_iv_equilibrium(p)),
      'M03':(DATA/'M03_market_monthly.csv',lambda p:m03_elasticity(p)),
    }
    for name,(path,fn) in tasks.items():
        if not path.exists():results[name]={'status':'BLOCKED_MISSING_REAL_DATA','expected_file':str(path.relative_to(ROOT))};continue
        try:results[name]=fn(path)
        except Exception as e:results[name]={'status':'FAILED_VALIDATION','error':str(e)}
    z,x,y=DATA/'M06_Z.csv',DATA/'M06_x.csv',DATA/'M06_Y.csv';px=DATA/'M06_published_x.csv'
    if not all(p.exists() for p in (z,x,y)):
        results['M06']={'status':'BLOCKED_MISSING_FULL_IO_TABLE','required_files':[str(p.relative_to(ROOT)) for p in (z,x,y)]}
    else:
        try:_,results['M06']=build_and_validate(z,x,y,px if px.exists() else None)
        except Exception as e:results['M06']={'status':'FAILED_VALIDATION','error':str(e)}
    report={'stage':'ECONOMIA stage 2','results':results,
            'real_empirical_models_completed':sum(1 for v in results.values() if str(v.get('status','')).startswith('PASS') or v.get('status') in {'APPARENT_CONSUMPTION_ONLY','DESCRIPTIVE_REDUCED_FORM'}),
            'warning':'A successful code run is not independent external validation.'}
    (ROOT/'stage2_empirical_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2));return report
if __name__=='__main__':run()
