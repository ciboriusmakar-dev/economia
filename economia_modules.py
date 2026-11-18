"""Единый программный интерфейс M01–M14 ECONOMIA."""
from __future__ import annotations
import csv, tempfile
from pathlib import Path
from economia_engine import execute_model
from economia_extended_models import m07_regression,m08_difference_in_differences,m09_forecast,m10_resource_optimisation,m11_linear_multi_market,m12_inventory,m13_max_flow,m14_risk
from m01_prodcom_balance import calculate as _m01_calculate
from m02_m03_market_models import m02_iv_equilibrium,m03_elasticity
from m04_m05_models import estimate_m04,estimate_m05
from io_matrix_builder import build_and_validate
from economia_spec_models import m02_demand_activity,m03_price_analysis,m04_productivity,m07_macro,m11_market_comparison
from economia_spec_models_ops import m09_forecasting,m12_inventory_analysis,m13_logistics,m14_scenarios
from economia_spec_models_more import m05_cost_analysis,m06_input_output,m08_causal_analysis,m10_production_optimisation

MODEL_NAMES={
'M01':'Анализ товаров и товарных балансов','M02':'Анализ спроса и рыночной активности','M03':'Анализ цен','M04':'Анализ производительности','M05':'Анализ себестоимости и затрат','M06':'Межотраслевой анализ','M07':'Макроэкономический анализ','M08':'Причинный анализ','M09':'Прогнозирование','M10':'Оптимизация производства','M11':'Анализ нескольких рынков','M12':'Управление запасами','M13':'Логистика и транспортные потоки','M14':'Экономические риски'}

def _tmp_csv(rows):
    f=tempfile.NamedTemporaryFile(mode='w',newline='',encoding='utf-8',suffix='.csv',delete=False)
    try:
        if not rows: raise ValueError('Пустой набор записей')
        fields=list(dict.fromkeys(k for row in rows for k in row.keys()))
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows);f.close();return Path(f.name)
    except Exception:
        f.close();Path(f.name).unlink(missing_ok=True);raise

def _m01(records,**p):
    path=_tmp_csv(records)
    try:return _m01_calculate(path)
    finally:path.unlink(missing_ok=True)
def _m02(records,**p):
    path=_tmp_csv(records)
    try:return m02_iv_equilibrium(path,**p)
    finally:path.unlink(missing_ok=True)
def _m03(records,**p):
    path=_tmp_csv(records)
    try:return m03_elasticity(path,**p)
    finally:path.unlink(missing_ok=True)
def _m04(records,**p):
    path=_tmp_csv(records)
    try:return estimate_m04(path,**p)
    finally:path.unlink(missing_ok=True)
def _m05(records,**p):
    path=_tmp_csv(records)
    try:return estimate_m05(path,**p)
    finally:path.unlink(missing_ok=True)
def _m06(records,**p):
    cfg=records[0]
    import numpy as np
    ids=cfg['industry_ids']; Z=np.asarray(cfg['Z'],float); x=np.asarray(cfg['gross_output'],float); y=np.asarray(cfg['domestic_final_demand'],float)
    if Z.shape!=(len(ids),len(ids)) or x.shape!=(len(ids),) or y.shape!=(len(ids),):raise ValueError('Размеры Z, выпуска и конечного спроса не согласованы')
    if len(set(ids))!=len(ids):raise ValueError('Повторяются коды отраслей')
    if not np.isfinite(Z).all() or not np.isfinite(x).all() or not np.isfinite(y).all() or (Z<0).any() or (x<=0).any() or (y<0).any():raise ValueError('Недопустимые значения в матрице Z, выпуске или спросе')
    A=Z/x[np.newaxis,:];rho=float(max(abs(np.linalg.eigvals(A))))
    if rho>=1:raise ValueError(f'Система непродуктивна: rho(A)={rho}')
    xm=np.linalg.solve(np.eye(len(ids))-A,y)
    residual=float(np.max(np.abs(xm-x)/np.maximum(np.abs(x),1e-12)))
    return {'n_industries':len(ids),'industry_ids':ids,'A':A.tolist(),'leontief_inverse':np.linalg.inv(np.eye(len(ids))-A).tolist(),'calculated_output':xm.tolist(),'rho_A':rho,'condition_number':float(np.linalg.cond(np.eye(len(ids))-A)),'output_reconstruction_max_relative_error':residual,'status':'PASS_MATHEMATICAL_RECONSTRUCTION' if residual<=p.get('tolerance',1e-8) else 'FAIL_RECONSTRUCTION','warning':'Математическая реконструкция не заменяет независимую сверку с опубликованной полной таблицей'}

def _dispatch(spec_fn,legacy_fn=None,legacy_name=None):
    """По умолчанию — метод по спецификации; прежний метод доступен как method=<legacy_name>."""
    def run(records,**p):
        method=p.pop('method','spec')
        if method=='spec': return spec_fn(records,**p)
        if legacy_fn is not None and method==legacy_name: return legacy_fn(records,**p)
        allowed=['spec']+([legacy_name] if legacy_name else [])
        raise ValueError(f'Неизвестный метод «{method}»; доступны: {", ".join(allowed)}')
    return run

MODEL_FUNCTIONS={'M01':_m01,'M02':_dispatch(m02_demand_activity,_m02,'iv'),'M03':_dispatch(m03_price_analysis,_m03,'elasticity'),'M04':_dispatch(m04_productivity,_m04,'production_function'),'M05':_dispatch(m05_cost_analysis,_m05,'cost_function'),'M06':_dispatch(m06_input_output,_m06,'leontief_basic'),'M07':_dispatch(m07_macro,m07_regression,'regression'),'M08':_dispatch(m08_causal_analysis,m08_difference_in_differences,'did_basic'),'M09':_dispatch(m09_forecasting,m09_forecast,'baselines'),'M10':_dispatch(m10_production_optimisation,m10_resource_optimisation,'linprog'),'M11':_dispatch(m11_market_comparison,m11_linear_multi_market,'equilibrium'),'M12':_dispatch(m12_inventory_analysis,m12_inventory,'simulation'),'M13':_dispatch(m13_logistics,m13_max_flow,'max_flow'),'M14':_dispatch(m14_scenarios,m14_risk,'historical_risk')}

def run_model(model_id,dataset,parameters=None,mode='real'):
    if model_id not in MODEL_FUNCTIONS: raise KeyError(f'Неизвестная модель {model_id}; доступны {", ".join(MODEL_FUNCTIONS)}')
    return execute_model(model_id,MODEL_FUNCTIONS[model_id],dataset,parameters,mode=mode,version='1.9.5').to_dict()

def model_catalog():
    return [{'model_id':k,'name':v,'version':'1.9.5','interface':'dataset.records + parameters','status':'implemented; empirical status depends on source data'} for k,v in MODEL_NAMES.items()]
