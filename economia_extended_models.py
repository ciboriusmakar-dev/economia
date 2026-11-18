"""Расчётные ядра M07–M14. Все функции работают только с переданными данными."""
from __future__ import annotations
import math
import numpy as np
from scipy.optimize import linprog
from scipy.stats import norm


def _finite_matrix(x, name):
    a=np.asarray(x,dtype=float)
    if not np.isfinite(a).all(): raise ValueError(f'{name}: есть пропуски или нечисловые значения')
    return a

def m07_regression(records, y='y', x=('x',), add_intercept=True):
    X=_finite_matrix([[r[k] for k in x] for r in records],'X'); Y=_finite_matrix([r[y] for r in records],'y')
    if X.ndim==1: X=X.reshape(-1,1)
    if len(Y)<=X.shape[1]+int(add_intercept): raise ValueError('Недостаточно наблюдений относительно числа параметров')
    D=np.column_stack([np.ones(len(Y)),X]) if add_intercept else X
    rank=int(np.linalg.matrix_rank(D))
    if rank<D.shape[1]: raise ValueError('Матрица регрессоров неполного ранга: мультиколлинеарность')
    b=np.linalg.lstsq(D,Y,rcond=None)[0]; resid=Y-D@b; dof=len(Y)-D.shape[1]
    inv=np.linalg.inv(D.T@D); s2=float(resid@resid/dof); cov=s2*inv; se=np.sqrt(np.diag(cov))
    leverage=np.sum((D@inv)*D,axis=1); denom=np.maximum(1-leverage,1e-10)
    meat=D.T@(((resid/denom)**2)[:,None]*D)
    cov_hc3=inv@meat@inv; se_hc3=np.sqrt(np.maximum(np.diag(cov_hc3),0))
    t=b/se_hc3; r2=1-float(resid@resid)/float(((Y-Y.mean())**2).sum()) if np.var(Y)>0 else None
    return {'n':len(Y),'coefficients':b.tolist(),'standard_errors_iid':se.tolist(),'standard_errors_hc3':se_hc3.tolist(),'t_statistics_hc3':t.tolist(),'r_squared':r2,'residual_std':math.sqrt(s2),'rank':rank,'dof':dof,'interpretation':'Ассоциативная регрессия; HC3-ошибки устойчивы к гетероскедастичности, причинность не установлена'}

def m08_difference_in_differences(records, outcome='outcome', treated='treated', post='post', cluster=None):
    y=_finite_matrix([r[outcome] for r in records],'outcome'); t=_finite_matrix([r[treated] for r in records],'treated'); p=_finite_matrix([r[post] for r in records],'post')
    if not set(np.unique(t)).issubset({0.,1.}) or not set(np.unique(p)).issubset({0.,1.}): raise ValueError('treated и post должны быть бинарными 0/1')
    cells={(a,b):y[(t==a)&(p==b)] for a in (0.,1.) for b in (0.,1.)}
    if any(len(v)==0 for v in cells.values()): raise ValueError('Нужны наблюдения во всех четырёх группах treated×post')
    means={f'{int(a)}_{int(b)}':float(v.mean()) for (a,b),v in cells.items()}
    did=(means['1_1']-means['1_0'])-(means['0_1']-means['0_0'])
    X=np.column_stack([np.ones(len(y)),t,p,t*p]); inv=np.linalg.inv(X.T@X); beta=inv@X.T@y; resid=y-X@beta
    cluster_count=None; cluster_warning=None
    if cluster:
        groups=np.asarray([r[cluster] for r in records]); unique=np.unique(groups)
        if len(unique)<2: raise ValueError('Для кластерных ошибок требуется не менее двух кластеров')
        meat=np.zeros((4,4))
        for g in unique:
            ix=groups==g; score=X[ix].T@resid[ix]; meat+=np.outer(score,score)
        G=len(unique);N=len(y);K=4
        if N<=K: raise ValueError('Недостаточно остаточных степеней свободы для кластерной ошибки')
        correction=(G/(G-1))*((N-1)/(N-K))
        cov=correction*inv@meat@inv; se=float(np.sqrt(max(cov[3,3],0))); se_type='cluster';cluster_count=int(G)
        if G<30: cluster_warning='Мало кластеров: кластерные стандартные ошибки и обычный нормальный интервал могут быть неточны'
    else:
        dof=len(y)-4
        if dof<=0: raise ValueError('Недостаточно наблюдений для стандартной ошибки')
        s2=float(resid@resid/dof); cov=s2*inv; se=float(np.sqrt(max(cov[3,3],0))); se_type='homoskedastic'
    return {'n':len(y),'cell_means':means,'did_effect':float(beta[3]),'standard_error':se,'standard_error_type':se_type,'cluster_count':cluster_count,'approx_95pct_interval':[float(beta[3]-1.96*se),float(beta[3]+1.96*se)],'identification_status':'NOT_ESTABLISHED','required_checks':['параллельные тренды до воздействия','отсутствие предвосхищения','отсутствие одновременных различающихся воздействий','стабильность состава групп'],'warning':'Оценка разности разностей сама по себе не доказывает причинный эффект'+(f'; {cluster_warning}' if cluster_warning else '')}

def m09_forecast(records, value='value', time='period', horizon=1, min_train=5, season_length=12):
    rows=sorted(records,key=lambda r:r[time]); y=_finite_matrix([r[value] for r in rows],'value')
    if horizon<1 or min_train<2 or len(y)<min_train+horizon: raise ValueError('Недостаточно наблюдений для заданного горизонта и обучающего окна')
    errors={'naive':[],'drift':[]}
    if season_length>0 and len(y)>season_length+min_train: errors['seasonal_naive']=[]
    for end in range(min_train,len(y)):
        train=y[:end]; actual=y[end]
        errors['naive'].append(float(actual-train[-1]))
        drift=train[-1]+(train[-1]-train[0])/(len(train)-1)
        errors['drift'].append(float(actual-drift))
        if 'seasonal_naive' in errors and end>=season_length: errors['seasonal_naive'].append(float(actual-train[-season_length]))
    metrics={k:{'mae':float(np.mean(np.abs(v))),'rmse':float(np.sqrt(np.mean(np.square(v)))),'n':len(v)} for k,v in errors.items() if v}
    selected=min(metrics,key=lambda k:metrics[k]['mae'])
    if selected=='naive': forecast=[float(y[-1])]*horizon
    elif selected=='drift':
        step=(y[-1]-y[0])/(len(y)-1);forecast=[float(y[-1]+step*h) for h in range(1,horizon+1)]
    else: forecast=[float(y[-season_length+((h-1)%season_length)]) for h in range(1,horizon+1)]
    return {'n':len(y),'selected_baseline':selected,'forecast':forecast,'rolling_origin_metrics':metrics,'backtest_origins':len(errors[selected]),'warning':'Выбор между простыми базовыми линиями по скользящей проверке; это не структурный прогноз и не гарантия будущей точности'}

def m10_resource_optimisation(records, objective='profit', constraints='constraints', bounds='bounds', maximize=True):
    cfg=records[0] if isinstance(records,list) and len(records)==1 else records
    c=_finite_matrix(cfg[objective],'objective')
    A=_finite_matrix(cfg[constraints]['A_ub'],'A_ub'); b=_finite_matrix(cfg[constraints]['b_ub'],'b_ub')
    if A.ndim!=2 or A.shape[1]!=len(c) or b.shape!=(A.shape[0],): raise ValueError('Несовместимые размеры целевой функции и ограничений')
    Aeq=cfg[constraints].get('A_eq'); beq=cfg[constraints].get('b_eq')
    if (Aeq is None) != (beq is None): raise ValueError('A_eq и b_eq должны задаваться вместе')
    if Aeq is not None:
        Aeq=_finite_matrix(Aeq,'A_eq'); beq=_finite_matrix(beq,'b_eq')
        if Aeq.ndim!=2 or Aeq.shape[1]!=len(c) or beq.shape!=(Aeq.shape[0],): raise ValueError('Несовместимые размеры равенств')
    bd=cfg.get(bounds,[(0,None)]*len(c)); result=linprog(-c if maximize else c,A_ub=A,b_ub=b,A_eq=Aeq,b_eq=beq,bounds=bd,method='highs')
    if not result.success: return {'solver_status':result.message,'solver_code':int(result.status),'optimal':False,'status':f'FAIL_SOLVER_{int(result.status)}'}
    return {'solver_status':'optimal','optimal':True,'decision_variables':result.x.tolist(),'objective_value':float(c@result.x),'slack':result.ineqlin.residual.tolist(),'marginals':result.ineqlin.marginals.tolist(),'warning':'Оптимум условен на корректности заданных коэффициентов и ограничений'}

def m11_linear_multi_market(records, demand_intercept='a', demand_matrix='B', supply_intercept='c', supply_matrix='S'):
    cfg=records[0] if isinstance(records,list) and len(records)==1 else records
    a=_finite_matrix(cfg[demand_intercept],'a'); B=_finite_matrix(cfg[demand_matrix],'B'); c=_finite_matrix(cfg[supply_intercept],'c'); S=_finite_matrix(cfg[supply_matrix],'S')
    n=len(a)
    if B.shape!=(n,n) or S.shape!=(n,n) or c.shape!=(n,): raise ValueError('Матрицы спроса/предложения и векторы должны иметь согласованные размеры')
    # qd = a - Bp; qs = c + Sp => (B+S)p = a-c
    M=B+S
    if np.linalg.matrix_rank(M)<n: raise ValueError('Равновесие не идентифицируется: матрица B+S вырождена')
    p=np.linalg.solve(M,a-c); q=a-B@p
    if (p<0).any() or (q<0).any(): raise ValueError('Решение содержит отрицательные цены или количества')
    return {'prices':p.tolist(),'quantities':q.tolist(),'market_clearing_residual':float(np.max(np.abs((a-B@p)-(c+S@p)))),'condition_number':float(np.linalg.cond(M))}

def m12_inventory(records, initial_stock=0.0, stock='production', demand='demand', reorder_point=None, order_quantity=0.0, lead_time=1):
    stock_now=float(initial_stock)
    if stock_now<0 or order_quantity<0 or lead_time<1: raise ValueError('Запасы и заказ неотрицательны, срок поставки не менее одного периода')
    pipeline={}; path=[]; total_shortage=0.; total_sales=0.; total_orders=0.
    for i,r in enumerate(records):
        arriving=float(pipeline.pop(i,0.0)); stock_now+=arriving
        prod=float(r[stock]); dem=float(r[demand])
        if not math.isfinite(prod+dem) or prod<0 or dem<0: raise ValueError(f'Период {i}: выпуск и спрос должны быть конечными и неотрицательными')
        available=stock_now+prod; sales=min(available,dem); shortage=dem-sales; stock_now=available-sales
        order=order_quantity if reorder_point is not None and stock_now<=reorder_point else 0.
        if order: pipeline[i+lead_time]=pipeline.get(i+lead_time,0.)+order; total_orders+=order
        path.append({'period':r.get('period',i),'arrivals':arriving,'sales':sales,'ending_stock':stock_now,'unmet_demand':shortage,'new_order':order,'pipeline':dict(pipeline)})
        total_shortage+=shortage;total_sales+=sales
    return {'periods':path,'total_sales':total_sales,'total_unmet_demand':total_shortage,'ending_stock':stock_now,'orders_in_transit':sum(pipeline.values()),'total_orders_placed':total_orders,'warning':'Упрощённая модель: срок поставки фиксирован; нет потерь, порчи, ограничений поставщика и стохастических задержек'}

def m13_max_flow(records, source, sink, edges='edges'):
    cfg=records[0] if isinstance(records,list) and len(records)==1 else records
    es=cfg[edges]; nodes=sorted({u for u,v,cap in es}|{v for u,v,cap in es})
    if source not in nodes or sink not in nodes or source==sink: raise ValueError('Источник и сток должны быть различными узлами сети')
    # LP: maximize sum source outgoing flow; conservation at intermediate nodes.
    n=len(es); c=np.zeros(n)
    for j,(u,v,cap) in enumerate(es):
        if not math.isfinite(float(cap)) or cap<0: raise ValueError('Пропускная способность должна быть конечной и неотрицательной')
        if u==source:c[j]=-1
    Aeq=[];beq=[]
    for node in nodes:
        if node in (source,sink): continue
        row=np.zeros(n)
        for j,(u,v,cap) in enumerate(es):
            if v==node:row[j]+=1
            if u==node:row[j]-=1
        Aeq.append(row);beq.append(0.)
    res=linprog(c,A_eq=np.array(Aeq) if Aeq else None,b_eq=np.array(beq) if beq else None,bounds=[(0,float(e[2])) for e in es],method='highs')
    if not res.success: raise RuntimeError(res.message)
    flows=[{'from':u,'to':v,'flow':float(res.x[j]),'capacity':float(cap)} for j,(u,v,cap) in enumerate(es)]
    return {'max_flow':float(-res.fun),'edge_flows':flows,'solver_status':'optimal'}

def m14_risk(records, value='value', confidence=.95, weights=None):
    x=_finite_matrix([r[value] for r in records],'value')
    if not 0<confidence<1: raise ValueError('confidence должен быть между 0 и 1')
    if weights is None: w=np.ones(len(x))/len(x)
    else:
        w=_finite_matrix(weights,'weights')
        if w.shape!=x.shape or (w<0).any() or not np.isclose(w.sum(),1): raise ValueError('Вероятностные веса должны быть неотрицательны и суммироваться в 1')
    mean=float(w@x); var=float(w@((x-mean)**2)); order=np.argsort(x); xs=x[order]; ws=w[order]; cum=np.cumsum(ws)
    qi=min(np.searchsorted(cum,confidence),len(xs)-1); q=float(xs[qi]); tail_probability=1-confidence
    # Exact weighted upper-tail expectation, taking only the required fraction at the quantile.
    above=xs>q; mass_above=float(ws[above].sum()); value_above=float(ws[above]@xs[above]) if mass_above else 0.0
    mass_at_q=float(ws[xs==q].sum()); mass_from_q=max(0.0,tail_probability-mass_above)
    cvar=(value_above+q*min(mass_at_q,mass_from_q))/tail_probability
    return {'mean':mean,'standard_deviation':math.sqrt(var),'quantile':q,'confidence':confidence,'upper_tail_probability':tail_probability,'expected_shortfall_upper_tail':float(cvar),'n':len(x),'warning':'Историческая выборка не гарантирует оценку редких хвостовых событий'}
