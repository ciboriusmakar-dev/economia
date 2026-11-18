"""Empirical M04 production function and M05 cost structure from canonical STAN/IOT data."""
from __future__ import annotations
import csv,json
from pathlib import Path
import numpy as np

def read_long(path):
    with open(path,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def _ols_cluster(X,y,groups):
    XtX=X.T@X
    if np.linalg.matrix_rank(X)<X.shape[1]: raise ValueError('Регрессоры линейно зависимы; оценка неидентифицирована')
    inv=np.linalg.inv(XtX);b=inv@X.T@y;u=y-X@b
    meat=np.zeros((X.shape[1],X.shape[1]))
    for g in sorted(set(groups)):
        ix=np.asarray([v==g for v in groups]);score=X[ix].T@u[ix];meat+=np.outer(score,score)
    G=len(set(groups));N=len(y);K=X.shape[1]
    if N<=K: raise ValueError('M04: недостаточно остаточных степеней свободы для оценки дисперсии')
    if G<2: raise ValueError('M04: кластерные стандартные ошибки требуют не менее двух отраслевых кластеров')
    correction=(G/(G-1))*((N-1)/(N-K))
    cov=correction*inv@meat@inv
    return b,np.sqrt(np.maximum(np.diag(cov),0)),u,G

def estimate_m04(path, min_obs=30):
    """CSV columns: country,industry,year,variable,value,flag. Variables: VA,K_STOCK,LABOUR."""
    rows=read_long(path); panel={}
    for r in rows:
        if (r.get('flag') or '').strip():  # primary fit uses only unflagged official observations
            continue
        try: value=float(r['value'])
        except (TypeError,ValueError): continue
        if not np.isfinite(value): continue
        key=(r['country'],r['industry'],r['year']);panel.setdefault(key,{})[r['variable'].upper()]=value
    obs=[]
    for key,v in panel.items():
        if all(k in v and v[k]>0 for k in ('VA','K_STOCK','LABOUR')):obs.append((key,v))
    if len(obs)<min_obs:raise ValueError(f'M04: требуется минимум {min_obs} полных положительных наблюдений, получено {len(obs)}')
    industries=sorted({k[1] for k,v in obs});years=sorted({int(k[2]) for k,v in obs})
    # Industry and year fixed effects; omit first category to avoid dummy trap.
    X0=np.column_stack([np.ones(len(obs)),[np.log(v['K_STOCK']) for k,v in obs],[np.log(v['LABOUR']) for k,v in obs]])
    d_ind=np.asarray([[1.0 if k[1]==c else 0.0 for c in industries[1:]] for k,v in obs])
    d_year=np.asarray([[1.0 if int(k[2])==t else 0.0 for t in years[1:]] for k,v in obs])
    X=np.column_stack([X0,d_ind,d_year]);y=np.log([v['VA'] for k,v in obs]);groups=[k[1] for k,v in obs]
    b,se,u,cluster_count=_ols_cluster(X,y,groups);pred=X@b
    sst=float(((y-y.mean())**2).sum());r2=1-float(u@u)/sst if sst else None
    return {"model":"M04","n":len(obs),"industries":len(industries),"years":[min(years),max(years)],
            "capital_elasticity":float(b[1]),"capital_elasticity_cluster_se":float(se[1]),
            "labour_elasticity":float(b[2]),"labour_elasticity_cluster_se":float(se[2]),
            "returns_to_scale":float(b[1]+b[2]),"r_squared_with_industry_and_year_fixed_effects":r2,
            "residual_rmse_log":float(np.sqrt(np.mean(u*u))),
            "cluster_count":cluster_count,
            "warning":('Мало отраслевых кластеров: кластерные стандартные ошибки могут быть неточны' if cluster_count<30 else None),
            "status":"ESTIMATED_WITH_FLAGS_EXCLUDED; NOT_CAUSAL"}

def estimate_m05(path, tolerance=1e-4):
    """CSV columns: industry,output,intermediate_consumption,compensation,fixed_capital_consumption,net_operating_surplus,other_taxes,year.

    tolerance is the maximum absolute reconciliation residual divided by gross output.
    """
    rows=read_long(path);out=[]
    if not rows: raise ValueError('M05: пустой набор данных')
    if not np.isfinite(tolerance) or tolerance<0: raise ValueError('M05: tolerance должен быть конечным и неотрицательным')
    for r in rows:
        vals={k:float(r[k]) for k in ('output','intermediate_consumption','compensation','fixed_capital_consumption','net_operating_surplus','other_taxes')}
        if not all(np.isfinite(v) for v in vals.values()): raise ValueError('M05: все компоненты должны быть конечными числами')
        if vals['output']<=0 or any(vals[k]<0 for k in ('intermediate_consumption','compensation','fixed_capital_consumption')):raise ValueError('M05: недопустимые компоненты затрат')
        total=sum(vals[k] for k in ('intermediate_consumption','compensation','fixed_capital_consumption','net_operating_surplus','other_taxes'))
        residual=vals['output']-total
        relative=abs(residual)/vals['output']
        out.append({"industry":r['industry'],"year":int(r['year']),"output":vals['output'],
                    "intermediate_consumption_share":vals['intermediate_consumption']/vals['output'],
                    "compensation_share":vals['compensation']/vals['output'],
                    "capital_consumption_share":vals['fixed_capital_consumption']/vals['output'],
                    "net_operating_surplus_share":vals['net_operating_surplus']/vals['output'],
                    "other_taxes_share":vals['other_taxes']/vals['output'],
                    "reconciliation_residual":residual,"relative_abs_reconciliation_residual":relative})
    max_abs=max(abs(r['reconciliation_residual']) for r in out)
    max_rel=max(r['relative_abs_reconciliation_residual'] for r in out)
    return {"model":"M05","n_industry_year":len(out),"rows":out,
            "max_abs_reconciliation_residual":max_abs,
            "max_relative_abs_reconciliation_residual":max_rel,
            "reconciliation_tolerance":tolerance,
            "status":"PASS_COST_RECONCILIATION" if max_rel<=tolerance else "FAIL_COST_RECONCILIATION"}
