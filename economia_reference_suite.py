"""Versioned synthetic reference fixtures for ECONOMIA model families.
Synthetic fixtures establish implementation consistency only, not empirical validity.
"""
from __future__ import annotations
import json
from economia_core import goods_balance, solve_leontief
from economia_models import (linear_market_equilibrium, price_elasticity, cobb_douglas,
    cost_metrics, ols_simple, did_effect, naive_forecast, lp_resource_allocation,
    two_market_equilibrium, agent_market_step, supply_chain_flow, uncertainty_discrete,
    multi_agent_exchange)

FIXTURES = [
 {'id':'REF-M01','model':'M01','name':'Товарный баланс','type':'synthetic','input':{'production':100,'imports':20,'opening_stocks':5,'intermediate_use':40,'final_use':60,'exports':15,'losses':2,'closing_stocks':8},'oracle':{'residual':0.0,'balanced':True}},
 {'id':'REF-M02','model':'M02','name':'Линейный рынок','type':'synthetic','input':{'ad':100,'bd':2,'a_s':10,'b_s':3},'oracle':{'price':18.0,'quantity':64.0}},
 {'id':'REF-M03','model':'M03','name':'Эластичность спроса','type':'synthetic','input':{'dq_dp':-4,'price':10,'quantity':80},'oracle':{'elasticity':-0.5}},
 {'id':'REF-M04','model':'M04','name':'Производственная функция','type':'synthetic','input':{'A':2,'K':16,'L':9,'alpha':0.5,'beta':0.5},'oracle':{'output':24.0}},
 {'id':'REF-M05','model':'M05','name':'Себестоимость','type':'synthetic','input':{'fixed_cost':100,'variable_cost':300,'output':20},'oracle':{'total_cost':400,'average_cost':20}},
 {'id':'REF-M06','model':'M06','name':'Леонтьев','type':'synthetic','input':{'A':[[0.2,0.1],[0.1,0.2]],'final_demand':[100,80]},'oracle':{'output':[139.68253968253967,117.46031746031746]}},
 {'id':'REF-M07','model':'M07','name':'Линейная регрессия','type':'synthetic','input':{'x':[1,2,3,4],'y':[3,5,7,9]},'oracle':{'intercept':1,'slope':2,'sse':0}},
 {'id':'REF-M08','model':'M08','name':'Разность разностей','type':'synthetic','input':{'treat_before':10,'treat_after':16,'control_before':8,'control_after':11},'oracle':{'effect':3}},
 {'id':'REF-M09','model':'M09','name':'Наивный прогноз','type':'synthetic','input':{'train':[10,12,11,14],'horizon':2},'oracle':{'forecast':[14,14]}},
 {'id':'REF-M10','model':'M10','name':'Распределение ресурсов','type':'synthetic','input':{},'oracle':{'objective':9,'x':1,'y':3}},
 {'id':'REF-M11','model':'M11','name':'Два взаимосвязанных рынка','type':'synthetic','input':{},'oracle':{'q1':3.6683417085427137,'q2':3.316582914572864}},
 {'id':'REF-M12','model':'M12','name':'Агентное состояние запасов','type':'synthetic','input':{'inventory':3,'production':5,'demand':6},'oracle':{'sales':6,'ending_inventory':2,'unmet_demand':0}},
 {'id':'REF-M13','model':'M13','name':'Поток цепочки поставок','type':'synthetic','input':{},'oracle':{'max_deliverable':10}},
 {'id':'REF-M14','model':'M14','name':'Дискретная неопределённость','type':'synthetic','input':{'values':[0,10],'probabilities':[0.25,0.75]},'oracle':{'mean':7.5,'variance':18.75}},
]


def run_reference_suite():
    out=[]
    for f in FIXTURES:
        i=f['input']; o=f['oracle']; passed=False; actual={}
        if f['model']=='M01':
            r=goods_balance(**i); actual={'residual':r.residual,'balanced':r.is_balanced}; passed=r.is_balanced and abs(r.residual-o['residual'])<1e-9
        elif f['model']=='M02':
            actual=linear_market_equilibrium(**i); passed=abs(actual['price']-o['price'])<1e-9 and abs(actual['quantity']-o['quantity'])<1e-9
        elif f['model']=='M03':
            actual={'elasticity':price_elasticity(**i)}; passed=abs(actual['elasticity']-o['elasticity'])<1e-9
        elif f['model']=='M04':
            actual={'output':cobb_douglas(**i)}; passed=abs(actual['output']-o['output'])<1e-9
        elif f['model']=='M05':
            actual=cost_metrics(**i); passed=all(abs(actual[k]-o[k])<1e-9 for k in o)
        elif f['model']=='M06':
            r=solve_leontief(i['A'],i['final_demand']); actual={'output':list(r.output)}; passed=all(abs(a-b)<1e-8 for a,b in zip(actual['output'],o['output']))
        elif f['model']=='M07':
            actual=ols_simple(i['x'],i['y']); passed=all(abs(actual[k]-o[k])<1e-8 for k in o)
        elif f['model']=='M08':
            actual={'effect':did_effect(**i)}; passed=actual['effect']==o['effect']
        elif f['model']=='M09':
            actual={'forecast':naive_forecast(i['train'],i['horizon'])}; passed=actual['forecast']==o['forecast']
        elif f['model']=='M10':
            actual=lp_resource_allocation(); passed=abs(actual['objective']-o['objective'])<1e-8 and abs(actual['x']-o['x'])<1e-8 and abs(actual['y']-o['y'])<1e-8
        elif f['model']=='M11':
            actual=two_market_equilibrium(); passed=abs(actual['q1']-o['q1'])<1e-8 and abs(actual['q2']-o['q2'])<1e-8
        elif f['model']=='M12':
            actual=agent_market_step(**i); passed=all(actual[k]==o[k] for k in o)
        elif f['model']=='M13':
            actual=supply_chain_flow(); passed=actual['max_deliverable']==o['max_deliverable']
        elif f['model']=='M14':
            actual=uncertainty_discrete(**i); passed=abs(actual['mean']-o['mean'])<1e-9 and abs(actual['variance']-o['variance'])<1e-9
        out.append({'fixture_id':f['id'],'model':f['model'],'passed':bool(passed),'actual':actual,'type':'synthetic'})
    return {'suite':'ECONOMIA-reference-suite-v1.1','count':len(out),'passed':sum(x['passed'] for x in out),'all_passed':all(x['passed'] for x in out),'tests':out,'warning':'Синтетические эталоны не являются эмпирической проверкой реальной экономики.'}

if __name__=='__main__': print(json.dumps(run_reference_suite(),ensure_ascii=False,indent=2))
