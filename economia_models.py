"""Small transparent reference implementations for ECONOMIA model tests.
These functions are pedagogical/benchmark implementations, not production estimators.
"""
from __future__ import annotations
import math
import numpy as np
from scipy.optimize import linprog


def linear_market_equilibrium(ad: float, bd: float, a_s: float, b_s: float):
    if bd <= 0 or b_s <= 0: raise ValueError('Наклоны должны обеспечивать убывающий спрос и возрастающее предложение')
    p = (ad - a_s) / (bd + b_s)
    q = ad - bd * p
    return {'price': p, 'quantity': q}


def price_elasticity(dq_dp: float, price: float, quantity: float):
    if price <= 0 or quantity <= 0: raise ValueError('Цена и количество должны быть положительными')
    return dq_dp * price / quantity


def cobb_douglas(A: float, K: float, L: float, alpha: float, beta: float):
    if min(A,K,L) <= 0 or min(alpha,beta) < 0: raise ValueError('Недопустимые параметры')
    return A * K**alpha * L**beta


def cost_metrics(fixed_cost: float, variable_cost: float, output: float):
    if output <= 0: raise ValueError('Выпуск должен быть положительным')
    total = fixed_cost + variable_cost
    return {'total_cost': total, 'average_cost': total/output}


def ols_simple(x, y):
    x=np.asarray(x,dtype=float); y=np.asarray(y,dtype=float)
    if x.ndim != 1 or y.shape != x.shape or len(x)<2: raise ValueError('Некорректная выборка')
    X=np.column_stack([np.ones(len(x)),x])
    beta=np.linalg.lstsq(X,y,rcond=None)[0]
    residual=y-X@beta
    return {'intercept':float(beta[0]),'slope':float(beta[1]),'sse':float(residual@residual)}


def did_effect(treat_before, treat_after, control_before, control_after):
    return (treat_after-treat_before)-(control_after-control_before)


def naive_forecast(train, horizon=1):
    if not train or horizon < 1: raise ValueError('Нужен непустой ряд и положительный горизонт')
    return [float(train[-1])]*horizon


def lp_resource_allocation():
    # Maximise 3*x + 2*y, subject to x+y<=4, 2*x+y<=5, x,y>=0.
    r=linprog(c=[-3,-2], A_ub=[[1,1],[2,1]], b_ub=[4,5], bounds=[(0,None),(0,None)], method='highs')
    if not r.success: raise RuntimeError(r.message)
    return {'x':float(r.x[0]),'y':float(r.x[1]),'objective':float(-r.fun), 'slack':r.ineqlin.residual.tolist()}


def two_market_equilibrium():
    # p1 = 10 - q1 - 0.2*q2; p2 = 8 - q2 - 0.1*q1; marginal costs are 2 and 1.
    # First-order conditions: 2*q1 + .2*q2 = 8; .1*q1 + 2*q2 = 7.
    q=np.linalg.solve([[2,.2],[.1,2]],[8,7])
    p1=10-q[0]-.2*q[1]; p2=8-q[1]-.1*q[0]
    return {'q1':float(q[0]),'q2':float(q[1]),'p1':float(p1),'p2':float(p2)}


def agent_market_step(inventory, production, demand):
    # Deterministic one-period inventory accounting.
    available=inventory+production
    sales=min(available,demand)
    return {'sales':sales,'ending_inventory':available-sales,'unmet_demand':max(0,demand-sales)}


def supply_chain_flow():
    # One source -> two routes -> one sink; capacities 7 and 5.
    return {'max_deliverable':min(7+5, 10), 'route_a':7, 'route_b':3}


def uncertainty_discrete(values, probabilities):
    v=np.asarray(values,dtype=float); p=np.asarray(probabilities,dtype=float)
    if v.shape != p.shape or np.any(p<0) or not np.isclose(p.sum(),1): raise ValueError('Некорректные вероятности')
    mean=float(np.sum(v*p)); variance=float(np.sum(((v-mean)**2)*p))
    return {'mean':mean,'variance':variance,'std':math.sqrt(variance)}


def multi_agent_exchange(initial_cash, initial_goods, offered_goods, desired_goods):
    # Aggregate accounting oracle for a closed toy exchange, no strategic behaviour claim.
    traded=min(initial_cash, offered_goods, desired_goods)
    return {'traded':traded,'cash_remaining':initial_cash-traded,'goods_remaining':initial_goods+offered_goods-traded}
