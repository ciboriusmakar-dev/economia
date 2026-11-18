"""M02 IV market equilibrium and M03 monthly price elasticity estimators.

Canonical input CSV columns: period,price_index,quantity_index,demand_shifter,
supply_shifter. M03 can run without instruments; M02 requires both excluded
shifters. Indexes are not physical units and estimates are reduced-form unless
valid exclusion restrictions are defended independently.
"""
from __future__ import annotations
import csv,math
import numpy as np

def read_market(path):
    with open(path,encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    rows.sort(key=lambda r:r['period'])
    periods=[r['period'] for r in rows]
    if len(periods)!=len(set(periods)): raise ValueError('Повторяющиеся месяцы в рыночном ряду')
    return rows

def _nw_se(X,u,max_lag=None):
    n,k=X.shape;inv=np.linalg.inv(X.T@X);L=max_lag if max_lag is not None else int(4*(n/100)**(2/9))
    meat=np.zeros((k,k));xu=X*u[:,None];meat+=xu.T@xu
    for lag in range(1,min(L,n-1)+1):
        weight=1-lag/(L+1);g=xu[lag:].T@xu[:-lag];meat+=weight*(g+g.T)
    cov=inv@meat@inv*n/(n-k)
    return np.sqrt(np.maximum(np.diag(cov),0))

def m03_elasticity(path,min_obs=36):
    rows=read_market(path);clean=[]
    for r in rows:
        p=float(r['price_index']);q=float(r['quantity_index'])
        if p>0 and q>0:clean.append((r['period'],p,q))
    if len(clean)<min_obs:raise ValueError(f'M03: требуется минимум {min_obs} месячных наблюдений, получено {len(clean)}')
    # Log-log with linear trend and calendar-month fixed effects. HAC errors.
    n=len(clean);months=[int(str(r[0])[-2:]) for r in clean]
    trend=np.arange(n,dtype=float);lp=np.log([r[1] for r in clean]);lq=np.log([r[2] for r in clean])
    dm=np.asarray([[1.0 if m==j else 0.0 for j in range(2,13)] for m in months])
    X=np.column_stack([np.ones(n),lp,trend,dm])
    if np.linalg.matrix_rank(X)<X.shape[1]:raise ValueError('M03: матрица регрессоров вырождена')
    b=np.linalg.lstsq(X,lq,rcond=None)[0];u=lq-X@b;se=_nw_se(X,u)
    denom=float(np.sum((lq-lq.mean())**2)); r2=float(1-(u@u)/denom) if denom>0 else None
    return {"model":"M03","n_months":n,"period_start":clean[0][0],"period_end":clean[-1][0],
            "log_price_coefficient":float(b[1]),"hac_standard_error":float(se[1]),
            "approx_95pct_interval":[float(b[1]-1.96*se[1]),float(b[1]+1.96*se[1])],
            "r_squared":r2,
            "warning":"Наблюдательная эластичность: цена эндогенна, индексы могут не совпадать по охвату. Не трактовать как причинную эластичность без идентификации.",
            "status":"DESCRIPTIVE_REDUCED_FORM"}

def m02_iv_equilibrium(path,min_obs=36):
    rows=read_market(path);cols=('price_index','quantity_index','demand_shifter','supply_shifter')
    data=[]
    for r in rows:
        v={c:float(r[c]) for c in cols}
        if all(math.isfinite(x) for x in v.values()) and v['price_index']>0 and v['quantity_index']>0:data.append((r['period'],v))
    if len(data)<min_obs:raise ValueError(f'M02: требуется минимум {min_obs} наблюдений с двумя инструментами, получено {len(data)}')
    # Simultaneous log-linear demand and supply: logQ = a_d + b_d logP + g_d Z_d;
    # logQ = a_s + b_s logP + g_s Z_s. Instrument logP with excluded shifters.
    lp=np.log([v['price_index'] for _,v in data]);lq=np.log([v['quantity_index'] for _,v in data])
    zd=np.log(np.asarray([v['demand_shifter'] for _,v in data]));zs=np.log(np.asarray([v['supply_shifter'] for _,v in data]))
    if np.any(~np.isfinite(zd)) or np.any(~np.isfinite(zs)):raise ValueError('Инструменты должны быть положительными')
    Z=np.column_stack([np.ones(len(data)),zd,zs])
    if np.linalg.matrix_rank(Z)<Z.shape[1]:raise ValueError('Инструменты не имеют независимой вариации')

    def partial_f(y, restricted, unrestricted):
        br=np.linalg.lstsq(restricted,y,rcond=None)[0]
        bu=np.linalg.lstsq(unrestricted,y,rcond=None)[0]
        ssr_r=float(np.sum((y-restricted@br)**2));ssr_u=float(np.sum((y-unrestricted@bu)**2))
        q=unrestricted.shape[1]-restricted.shape[1];df=len(y)-unrestricted.shape[1]
        if q<=0 or df<=0: raise ValueError('Недостаточно степеней свободы для F-проверки первой стадии')
        if ssr_u<=1e-14: return None
        return float(max(0.0,(ssr_r-ssr_u)/q)/(ssr_u/df))

    # Demand equation: demand shifter is included; supply shifter is excluded.
    # Supply equation: supply shifter is included; demand shifter is excluded.
    first_demand_f=partial_f(lp,np.column_stack([np.ones(len(data)),zd]),Z)
    first_supply_f=partial_f(lp,np.column_stack([np.ones(len(data)),zs]),Z)

    def estimate_2sls(included):
        X=np.column_stack([np.ones(len(data)),lp,included])
        Xhat=Z@np.linalg.pinv(Z)@X
        if np.linalg.matrix_rank(Xhat)<X.shape[1]: raise ValueError('Первая стадия не идентифицирует структурное уравнение')
        beta=np.linalg.lstsq(Xhat,lq,rcond=None)[0]
        residual=lq-X@beta
        # HAC sandwich for 2SLS scores; projected regressors preserve the IV moment structure.
        se=_nw_se(Xhat,residual)
        return beta,se

    bd,se_d=estimate_2sls(zd);bs,se_s=estimate_2sls(zs)
    return {"model":"M02","n_months":len(data),"demand_price_slope":float(bd[1]),"demand_price_slope_hac_se":float(se_d[1]),
            "supply_price_slope":float(bs[1]),"supply_price_slope_hac_se":float(se_s[1]),
            "first_stage_excluded_instrument_F_demand":first_demand_f,
            "first_stage_excluded_instrument_F_supply":first_supply_f,
            "warning":"Условная 2SLS-оценка с HAC-ошибками. Причинная интерпретация требует экономически обоснованных и валидных исключённых инструментов; сила инструмента не доказывает условие исключения.",
            "status":"IV_ESTIMATED_REQUIRES_INSTRUMENT_VALIDITY_REVIEW"}
