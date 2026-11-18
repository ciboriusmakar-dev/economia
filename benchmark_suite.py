"""Синтетический нагрузочный профиль всех M01–M14; не является эмпирическим тестом."""
from __future__ import annotations
import json,time,statistics,platform
import numpy as np
from economia_modules import run_model

def timed(fn,repeats=5):
    samples=[]
    for _ in range(repeats):
        t=time.perf_counter();fn();samples.append((time.perf_counter()-t)*1000)
    s=sorted(samples)
    return {'repeats':repeats,'median_ms':statistics.median(s),'p95_ms':s[min(len(s)-1,int(.95*len(s)))],'min_ms':min(s),'max_ms':max(s)}

def ds(mid,records): return {'dataset_id':'benchmark-'+mid,'source_id':'synthetic-benchmark','origin':'synthetic','data_mode':'simulation','records':records}
def run_model_sim(mid,records,params=None): return run_model(mid,ds(mid,records),params,mode='simulation')

def run():
    rng=np.random.default_rng(20261115); bench={}
    # M01
    r01=[]
    for i in range(1500):
        for ind,val in [('PRODQNT',100+i%17),('IMPQNT',20+i%5),('EXPQNT',10+i%3)]:r01.append({'country':'DE','year':2000+i//100,'product_code':f'P{i}','indicator':ind,'value':val,'unit':'T','flag':''})
    # M02/M03 monthly
    r02=[]
    for i in range(600):
        zd=1+.01*i+.1*np.sin(i);zs=1+.02*i+.1*np.cos(i);p=100*np.exp(.1*np.sin(i)+.05*np.cos(i));q=200*(p/100)**-.5*np.exp(.2*np.log(zd))
        r02.append({'period':f'{1975+i//12}-{i%12+1:02d}','price_index':p,'quantity_index':q,'demand_shifter':zd,'supply_shifter':zs})
    # M04/M05
    r04=[];r05=[]
    for i in range(15):
        for t in range(20):
            K=100+i*13+t*2.7+8*np.sin((i+1)*(t+1)/4);L=55+i*4.2+t*1.4+5*np.cos((i+2)*(t+1)/5);VA=(1+.04*i)*(K**.35)*(L**.65)
            for var,val in [('VA',VA),('K_STOCK',K),('LABOUR',L)]:r04.append({'country':'DE','industry':f'I{i}','year':2000+t,'variable':var,'value':val,'flag':''})
            out=1000+i*10+t; ic=out*.55;comp=out*.2;cap=out*.05;sur=out*.17;tax=out*.03
            r05.append({'industry':f'I{i}','year':2000+t,'output':out,'intermediate_consumption':ic,'compensation':comp,'fixed_capital_consumption':cap,'net_operating_surplus':sur,'other_taxes':tax})
    # M06, stable productive matrix
    n=100; ids=[f'I{i:03d}' for i in range(n)]; A=np.full((n,n),.0005);np.fill_diagonal(A,.04);x=np.full(n,1000.);Z=A*x[np.newaxis,:];y=(np.eye(n)-A)@x
    m06=[{'industry_ids':ids,'Z':Z.tolist(),'gross_output':x.tolist(),'domestic_final_demand':y.tolist()}]
    # M07/M08/M09
    r07=[{'x':float(v),'y':2+1.3*v+float(rng.normal(scale=.5))} for v in rng.normal(size=5000)]
    r08=[]
    for g in range(20):
        treated=g%2
        for post in (0,1):
            for j in range(25):r08.append({'unit':g,'treated':treated,'post':post,'outcome':10+2*treated+post+3*treated*post+float(rng.normal()),'period':post})
    r09=[{'period':f'{i:05d}','value':float(100+.02*i+np.sin(i/12))} for i in range(2000)]
    # M10/M11/M12/M13/M14
    n10=100; m10=[{'profit':rng.uniform(1,5,n10).tolist(),'constraints':{'A_ub':rng.uniform(0,1,(50,n10)).tolist(),'b_ub':rng.uniform(10,30,50).tolist()}}]
    n11=50;B=np.eye(n11)*1.2+np.ones((n11,n11))*.001;S=np.eye(n11)*.8;a=np.full(n11,10.);c=np.full(n11,1.)
    m11=[{'a':a.tolist(),'B':B.tolist(),'c':c.tolist(),'S':S.tolist()}]
    r12=[{'period':i,'production':float(100+i%7),'demand':float(98+i%9)} for i in range(10000)]
    edges=[('s',f'n{i}',10.) for i in range(100)]+[(f'n{i}','t',10.) for i in range(100)]
    m13=[{'edges':edges}]
    r14=[{'value':float(v)} for v in rng.normal(size=100000)]
    jobs={
      'M01':lambda:run_model_sim('M01',r01),
      'M02':lambda:run_model_sim('M02',r02),
      'M03':lambda:run_model_sim('M03',r02),
      'M04':lambda:run_model_sim('M04',r04,{'min_obs':100}),
      'M05':lambda:run_model_sim('M05',r05),
      'M06':lambda:run_model_sim('M06',m06),
      'M07':lambda:run_model_sim('M07',r07),
      'M08':lambda:run_model_sim('M08',r08,{'cluster':'unit'}),
      'M09':lambda:run_model_sim('M09',r09,{'horizon':6,'min_train':36,'season_length':12}),
      'M10':lambda:run_model_sim('M10',m10),
      'M11':lambda:run_model_sim('M11',m11),
      'M12':lambda:run_model_sim('M12',r12),
      'M13':lambda:run_model_sim('M13',m13,{'source':'s','sink':'t'}),
      'M14':lambda:run_model_sim('M14',r14),
    }
    for mid,fn in jobs.items():
        sample=fn()
        if sample['status'] not in {'COMPLETED','COMPLETED_WITH_WARNINGS'}:raise RuntimeError(f'{mid} benchmark fixture failed: {sample["errors"]}')
        bench[mid]=timed(fn)
    return {'profile':'all_models_synthetic_benchmark_v1','seed':20261115,'platform':platform.platform(),'python':platform.python_version(),'models':bench,'limitations':['Все входы синтетические; это тест производительности, а не эмпирическая валидация.','Время зависит от CPU, ОС, библиотек, памяти и фоновой нагрузки.','Размеры профиля не заменяют испытание на полных таблицах OECD/Eurostat.']}
if __name__=='__main__': print(json.dumps(run(),ensure_ascii=False,indent=2))
