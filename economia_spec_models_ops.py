"""Модули по спецификации: M09 прогнозирование, M12 запасы, M13 логистика, M14 риски и сценарии."""
from __future__ import annotations
import math, heapq
import numpy as np
from scipy.optimize import linprog
from scipy.stats import norm
from economia_spec_common import fnum, pct, num, sorted_rows, require_complete, table

# ---------------------------------------------------------------- M09
METHOD_RU = {'naive': '«как в прошлый раз»', 'drift': 'продолжение среднего прироста', 'seasonal_naive': '«как в тот же сезон год назад»',
             'linear_trend': 'линейный тренд', 'linear_trend_seasonal': 'линейный тренд с сезонностью',
             'holt': 'экспоненциальное сглаживание с трендом (Хольт)', 'holt_winters': 'сглаживание с трендом и сезонностью (Хольт — Уинтерс)'}

def _fc_naive(y, h, m): return np.full(h, y[-1])
def _fc_drift(y, h, m): return y[-1] + (y[-1] - y[0]) / (len(y) - 1) * np.arange(1, h + 1)
def _fc_snaive(y, h, m): return np.array([y[-m + ((k - 1) % m)] for k in range(1, h + 1)])
def _fc_lin(y, h, m):
    t = np.arange(len(y)); b = np.polyfit(t, y, 1); return np.polyval(b, len(y) - 1 + np.arange(1, h + 1))
def _fc_lin_seas(y, h, m):
    n = len(y); t = np.arange(n); D = lambda tt: np.column_stack([np.ones(len(tt)), tt] + [(tt % m == k).astype(float) for k in range(1, m)])
    b = np.linalg.lstsq(D(t), y, rcond=None)[0]; return D(n - 1 + np.arange(1, h + 1)) @ b
def _fc_holt(y, h, m):
    best = None
    for a in (.1, .3, .5, .7, .9):
        for be in (.05, .1, .2, .4):
            l, b = y[0], y[1] - y[0]; sse = 0.
            for v in y[1:]:
                e = v - (l + b); sse += e * e; ln = a * v + (1 - a) * (l + b); b = be * (ln - l) + (1 - be) * b; l = ln
            if best is None or sse < best[0]: best = (sse, l, b)
    return best[1] + best[2] * np.arange(1, h + 1)
def _fc_hw(y, h, m):
    n = len(y); best = None
    l0 = y[:m].mean(); b0 = (y[m:2 * m].mean() - y[:m].mean()) / m; s0 = list(y[:m] - l0)
    for a in (.1, .3, .5, .7):
        for be in (.01, .1, .3):
            for ga in (.1, .3, .5, .7):
                l, b, s = l0, b0, list(s0); sse = 0.
                for t in range(m, n):
                    f = l + b + s[t - m]; e = y[t] - f; sse += e * e
                    ln = a * (y[t] - s[t - m]) + (1 - a) * (l + b); bn = be * (ln - l) + (1 - be) * b
                    s.append(ga * (y[t] - ln) + (1 - ga) * s[t - m]); l, b = ln, bn
                if best is None or sse < best[0]: best = (sse, l, b, s)
    _, l, b, s = best
    return np.array([l + k * b + s[n - m + ((k - 1) % m)] for k in range(1, h + 1)])

def m09_forecasting(records, value='value', period='period', horizon=6, season_length=12, min_train=None, eval_horizon=1, max_origins=24):
    rows = sorted_rows(records, period); per = [str(r[period]) for r in rows]; require_complete(per, 'ряд для прогноза')
    y = np.array([num(r[value], value) for r in rows]); n = len(y); m = int(season_length)
    if horizon < 1 or eval_horizon < 1: raise ValueError('Горизонты должны быть не меньше 1')
    methods = {'naive': _fc_naive, 'drift': _fc_drift, 'linear_trend': _fc_lin}
    seasonal = m >= 2 and n >= 3 * m
    if seasonal: methods.update({'seasonal_naive': _fc_snaive, 'linear_trend_seasonal': _fc_lin_seas, 'holt_winters': _fc_hw})
    else: methods['holt'] = _fc_holt
    mt = min_train or (2 * m if seasonal else max(5, n // 2))
    first = mt; last_origin = n - eval_horizon
    if last_origin < first + 3: raise ValueError(f'Слишком короткий ряд для проверки на прошлом: {n} значений, нужно хотя бы {first + eval_horizon + 3}')
    origins = list(range(first, last_origin + 1))[-max_origins:]
    errs = {k: [] for k in methods}
    for end in origins:
        tr = y[:end]; tgt = y[end + eval_horizon - 1]
        for k, f in methods.items(): errs[k].append(float(tgt - f(tr, eval_horizon, m)[-1]))
    metrics = {}
    for k, e in errs.items():
        e = np.array(e); act = y[[o + eval_horizon - 1 for o in origins]]
        metrics[k] = {'mae': float(np.mean(np.abs(e))), 'rmse': float(np.sqrt(np.mean(e ** 2))), 'mape': float(np.mean(np.abs(e / act)) * 100) if (act != 0).all() else None, 'n': len(e)}
    best = min(metrics, key=lambda k: metrics[k]['rmse']); fc = methods[best](y, horizon, m)
    sd = metrics[best]['rmse']; hs = np.arange(1, horizon + 1); w = sd * np.sqrt(hs / eval_horizon)
    skill = 1 - metrics[best]['rmse'] / metrics['naive']['rmse'] if metrics['naive']['rmse'] > 0 else None
    # подписи будущих периодов, если периоды однотипные
    import re
    from economia_spec_common import period_index
    pi = period_index(per[-1]); last = per[-1]; future = [f'+{k}' for k in hs]
    if pi is not None and re.fullmatch(r'\d{4}-\d{1,2}', last): future = [f'{(pi + k) // 12}-{(pi + k) % 12 + 1:02d}' for k in hs]
    elif pi is not None and re.fullmatch(r'\d{4}-?[Qq][1-4]', last): future = [f'{(pi + k) // 4}-Q{(pi + k) % 4 + 1}' for k in hs]
    elif pi is not None and re.fullmatch(r'\d{4}', last): future = [str(pi + k) for k in hs]
    summ = [f'Лучший по проверке на прошлых данных метод: {METHOD_RU[best]}.',
            f'Проверка: {len(origins)} раз(а) модель «не видела» последующие значения; средняя ошибка (MAE) {fnum(metrics[best]["mae"], 2)}' + (f', в среднем {pct(metrics[best]["mape"])} от значения' if metrics[best]['mape'] is not None else '') + '.']
    warns = ['Это статистический прогноз по прошлой динамике, а не предсказание будущего; интервалы приблизительные (нормальное приближение по ошибкам проверки).']
    if skill is not None:
        if best == 'naive': summ.append('Ни один метод не оказался точнее простого «как в прошлый раз»: прогнозу по этому ряду доверять не стоит.'); warns.append('Нет метода лучше наивного.')
        else: summ.append(f'Ошибка меньше, чем у «как в прошлый раз», на {pct(skill * 100, 0)}.')
    summ.append(f'Прогноз на {horizon} периодов: {fnum(float(fc[0]), 1)} в {future[0]}, {fnum(float(fc[-1]), 1)} в {future[-1]}; коридор 80 % на конец: {fnum(float(fc[-1] - 1.2816 * w[-1]), 1)} … {fnum(float(fc[-1] + 1.2816 * w[-1]), 1)}.')
    hist = min(n, 3 * m if m >= 2 else 30); xs = per[-hist:] + future
    chart = {'type': 'line', 'title': 'История и прогноз (коридор 80 %)', 'x': xs,
             'series': [{'name': 'История', 'values': [float(v) for v in y[-hist:]] + [None] * horizon}, {'name': 'Прогноз', 'values': [None] * (hist - 1) + [float(y[-1])] + [float(v) for v in fc], 'dash': True}],
             'band': {'lo': [None] * hist + [float(a - 1.2816 * b) for a, b in zip(fc, w)], 'hi': [None] * hist + [float(a + 1.2816 * b) for a, b in zip(fc, w)]}}
    return {'n': n, 'selected_method': best, 'selected_method_ru': METHOD_RU[best], 'forecast': [float(v) for v in fc], 'future_periods': future,
            'interval80': {'lo': [float(a - 1.2816 * b) for a, b in zip(fc, w)], 'hi': [float(a + 1.2816 * b) for a, b in zip(fc, w)]},
            'interval95': {'lo': [float(a - 1.96 * b) for a, b in zip(fc, w)], 'hi': [float(a + 1.96 * b) for a, b in zip(fc, w)]},
            'backtest_metrics': metrics, 'backtest_origins': len(origins), 'skill_vs_naive': skill, 'summary_ru': summ, 'warnings': warns, 'chart': chart,
            'tables': {'methods': table(['Метод', 'MAE', 'RMSE', 'MAPE, %'], [[METHOD_RU[k], v['mae'], v['rmse'], v['mape']] for k, v in sorted(metrics.items(), key=lambda kv: kv[1]['rmse'])], 'Сравнение методов на прошлых данных'),
                       'forecast': table(['Период', 'Прогноз', 'Нижняя (80 %)', 'Верхняя (80 %)'], [[future[i], float(fc[i]), float(fc[i] - 1.2816 * w[i]), float(fc[i] + 1.2816 * w[i])] for i in range(horizon)], 'Прогноз')}}

# ---------------------------------------------------------------- M12
def m12_inventory_analysis(records, demand='demand', stock='stock', receipts=None, period='period', periods_per_year=12, lead_time=1,
                           holding_cost=None, order_cost=None, shortage_cost=None, service_level=0.95, reorder_point=None):
    """Анализ запасов: оборачиваемость, покрытие, потребность (страховой запас, точка заказа, EOQ), риск дефицита.
    holding_cost — затраты хранения единицы за период; order_cost — на один заказ; shortage_cost — убыток от единицы дефицита."""
    rows = sorted_rows(records, period); n = len(rows)
    if n < 3: raise ValueError('Нужно не менее 3 периодов')
    D = np.array([num(r[demand], demand) for r in rows]); S = np.array([num(r[stock], stock) for r in rows])
    if (D < 0).any() or (S < 0).any(): raise ValueError('Спрос и запас не могут быть отрицательными')
    if not 0.5 <= service_level < 1: raise ValueError('service_level должен быть от 0,5 до 1')
    L = float(lead_time); out = {}; summ = []; warns = []
    avg_s = float(S.mean()); mu = float(D.mean()); sd = float(D.std(ddof=1)); cv = sd / mu if mu > 0 else None
    out.update({'average_stock': avg_s, 'average_demand': mu, 'demand_sd': sd, 'demand_cv': cv})
    turnover = float(D.sum() / avg_s * periods_per_year / n) if avg_s > 0 else None
    cover = avg_s / mu if mu > 0 else None
    out.update({'turnover_per_year': turnover, 'days_of_cover': cover * 365 / periods_per_year if cover is not None else None})
    if turnover is not None: summ.append(f'Запас оборачивается {fnum(turnover, 1)} раз в год; хватает в среднем на {fnum(out["days_of_cover"], 0)} дней спроса.')
    if cv is not None: summ.append(f'Спрос колеблется: коэффициент вариации {fnum(cv, 2)} ({"высокий" if cv > 0.5 else "умеренный" if cv > 0.25 else "низкий"} разброс).')
    if receipts:
        Rr = np.array([num(r[receipts], receipts) for r in rows]); out['receipts_total'] = float(Rr.sum()); out['demand_total'] = float(D.sum())
        out['receipts_to_demand'] = float(Rr.sum() / D.sum()) if D.sum() > 0 else None
        summ.append(f'Поступило {fnum(Rr.sum(), 0)} при спросе {fnum(D.sum(), 0)} (поступления покрывают спрос на {pct(out["receipts_to_demand"] * 100, 0) if out["receipts_to_demand"] else "—"}).')
        out['stock_balance_residual'] = float(S[-1] - S[0] - (Rr[1:].sum() - D[1:].sum())); 
        if abs(out['stock_balance_residual']) > 0.01 * max(1.0, avg_s): warns.append(f'Баланс «запас_конец = запас_начало + поступления − продажи» не сходится: невязка {fnum(out["stock_balance_residual"], 1)} (потери, списания, ошибки учёта).')
    z = float(norm.ppf(service_level)); ss = z * sd * math.sqrt(L); rop = mu * L + ss
    out.update({'service_level': service_level, 'safety_stock': ss, 'recommended_reorder_point': rop, 'lead_time_periods': L})
    summ.append(f'Для уровня обслуживания {pct(service_level * 100, 0)} при сроке поставки {fnum(L, 0)} пер.: страховой запас {fnum(ss, 1)}, точка заказа {fnum(rop, 1)}.')
    if order_cost is not None and holding_cost:
        eoq = math.sqrt(2 * mu * order_cost / holding_cost); out['eoq'] = eoq
        summ.append(f'Экономичный размер заказа (EOQ): {fnum(eoq, 1)} за раз.')
    if holding_cost is not None: out['holding_cost_total'] = float(holding_cost * S.sum()); summ.append(f'Затраты хранения за период наблюдений: {fnum(out["holding_cost_total"], 0)}.')
    short = int((S <= 0).sum()); out['periods_with_zero_stock'] = short
    if short: summ.append(f'Запас был нулевым в {short} из {n} периодов.')
    if reorder_point is not None and sd > 0:
        zz = (reorder_point - mu * L) / (sd * math.sqrt(L)); risk = float(1 - norm.cdf(zz)); out['shortage_risk_at_given_reorder_point'] = risk
        summ.append(f'При вашей точке заказа {fnum(reorder_point, 1)} вероятность дефицита за срок поставки ≈ {pct(risk * 100, 1)} (нормальное приближение).')
        if shortage_cost: out['expected_shortage_cost_per_cycle'] = float(shortage_cost * sd * math.sqrt(L) * (norm.pdf(zz) - zz * (1 - norm.cdf(zz)))); summ.append(f'Ожидаемые потери от дефицита за цикл: {fnum(out["expected_shortage_cost_per_cycle"], 1)}.')
    warns.append('Нормальное приближение спроса и фиксированный срок поставки; для редких или «рваных» спросов оценки приблизительны.')
    per = [str(r[period]) for r in rows]
    out.update({'summary_ru': summ, 'warnings': warns,
                'tables': {'series': table(['Период', 'Спрос', 'Запас'], [[per[i], float(D[i]), float(S[i])] for i in range(n)], 'Спрос и запас')},
                'chart': {'type': 'line', 'title': 'Спрос и запас', 'x': per, 'series': [{'name': 'Запас', 'values': S.tolist()}, {'name': 'Спрос', 'values': D.tolist(), 'dash': True}]}})
    return out

# ---------------------------------------------------------------- M13
def _dijkstra(adj, src, dst, key):
    dist = {src: 0.0}; prev = {}; pq = [(0.0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, math.inf): continue
        if u == dst: break
        for v, e in adj.get(u, []):
            nd = d + e[key]
            if nd < dist.get(v, math.inf): dist[v] = nd; prev[v] = (u, e); heapq.heappush(pq, (nd, v))
    if dst not in dist: return None
    path = []; u = dst
    while u != src: p, e = prev[u]; path.append(e); u = p
    return dist[dst], path[::-1]

def m13_logistics(records, origin=None, destination=None, supply=None, demand=None):
    """records[0]['edges'] — список {from,to,distance,time,cost,capacity}: расстояние, время, стоимость единицы перевозки, пропускная способность.
    Маршруты (кратчайшие по расстоянию/времени/стоимости), узкие места, максимальный поток и
    распределение потоков с минимальной стоимостью при заданных предложении/спросе узлов."""
    cfg = records[0] if len(records) == 1 and 'edges' in records[0] else {'edges': records}
    E = []
    for i, e in enumerate(cfg['edges']):
        d = {'from': str(e['from']), 'to': str(e['to'])}
        for k in ('distance', 'time', 'cost', 'capacity'):
            if e.get(k) is not None:
                d[k] = num(e[k], k)
                if d[k] < 0: raise ValueError(f'Ребро {i}: «{k}» не может быть отрицательным')
        E.append(d)
    if not E: raise ValueError('Нет рёбер сети')
    origin = origin or cfg.get('origin'); destination = destination or cfg.get('destination')
    supply = supply or cfg.get('supply'); demand = demand or cfg.get('demand')
    nodes = sorted({e['from'] for e in E} | {e['to'] for e in E}); adj = {}
    for e in E: adj.setdefault(e['from'], []).append((e['to'], e))
    out = {'n_nodes': len(nodes), 'n_edges': len(E)}; summ = [f'Сеть: {len(nodes)} узлов, {len(E)} связей.']; warns = []; tables = {}
    if origin and destination:
        routes = {}
        for key, ru in (('distance', 'по расстоянию'), ('time', 'по времени'), ('cost', 'по стоимости')):
            if all(key in e for e in E):
                r = _dijkstra(adj, str(origin), str(destination), key)
                if r is None: routes[key] = None; warns.append(f'Маршрута {origin} → {destination} {ru} нет.'); continue
                tot, path = r; seq = [path[0]['from']] + [p['to'] for p in path]; routes[key] = {'total': tot, 'nodes': seq}
                summ.append(f'Кратчайший маршрут {ru}: {" → ".join(seq)} (итого {fnum(tot, 1)}).')
        out['routes'] = routes
        tables['routes'] = table(['Критерий', 'Маршрут', 'Итого'], [[{'distance': 'расстояние', 'time': 'время', 'cost': 'стоимость'}[k], ' → '.join(v['nodes']), v['total']] for k, v in routes.items() if v], 'Лучшие маршруты')
        if all('capacity' in e for e in E):
            n = len(E); idx = {nd: i for i, nd in enumerate(nodes)}; c = np.zeros(n)
            for j, e in enumerate(E):
                if e['from'] == str(origin): c[j] = -1
                if e['to'] == str(origin): c[j] += 1
            Aeq = []; beq = []
            for nd in nodes:
                if nd in (str(origin), str(destination)): continue
                row = np.zeros(n)
                for j, e in enumerate(E):
                    if e['to'] == nd: row[j] += 1
                    if e['from'] == nd: row[j] -= 1
                Aeq.append(row); beq.append(0.)
            r = linprog(c, A_eq=np.array(Aeq) if Aeq else None, b_eq=np.array(beq) if beq else None, bounds=[(0, e['capacity']) for e in E], method='highs')
            if r.success:
                fl = np.where(np.abs(r.x) < 1e-9, 0.0, r.x); out['max_flow'] = float(-r.fun)
                bott = [{'from': e['from'], 'to': e['to'], 'flow': float(fl[j]), 'capacity': e['capacity']} for j, e in enumerate(E) if e['capacity'] > 0 and fl[j] >= e['capacity'] - 1e-9]
                out['saturated_edges'] = bott
                summ.append(f'Максимальный поток {origin} → {destination}: {fnum(out["max_flow"], 1)}.' + (f' Узкие места (загружены на 100 %): ' + ', '.join(f'{b["from"]}→{b["to"]}' for b in bott) + '.' if bott else ''))
                tables['flows'] = table(['Откуда', 'Куда', 'Поток', 'Пропускная способность', 'Загрузка, %'], [[e['from'], e['to'], float(fl[j]), e['capacity'], float(fl[j] / e['capacity'] * 100) if e['capacity'] > 0 else None] for j, e in enumerate(E)], 'Потоки при максимальной пропускной способности')
    if supply and demand:
        sup = {str(k): num(v, 'supply') for k, v in supply.items()}; dem = {str(k): num(v, 'demand') for k, v in demand.items()}
        if not all('cost' in e for e in E): raise ValueError('Для оптимального распределения у каждого ребра нужна стоимость «cost»')
        ts, td = sum(sup.values()), sum(dem.values())
        if abs(ts - td) > 1e-9: raise ValueError(f'Предложение ({fnum(ts, 1)}) и спрос ({fnum(td, 1)}) должны быть равны; при неравенстве добавьте фиктивный узел или выровняйте объёмы')
        n = len(E); cst = np.array([e['cost'] for e in E]); Aeq = []; beq = []
        for nd in nodes:
            row = np.zeros(n)
            for j, e in enumerate(E):
                if e['from'] == nd: row[j] += 1
                if e['to'] == nd: row[j] -= 1
            Aeq.append(row); beq.append(sup.get(nd, 0.) - dem.get(nd, 0.))
        bnds = [(0, e.get('capacity')) for e in E]
        r = linprog(cst, A_eq=np.array(Aeq), b_eq=np.array(beq), bounds=bnds, method='highs')
        if not r.success: out['distribution'] = {'status': 'infeasible', 'message': r.message}; warns.append('Распределение невозможно при заданных пропускных способностях: сеть не может перевезти нужные объёмы.'); summ.append('Заданный спрос нельзя удовлетворить: не хватает пропускной способности сети.')
        else:
            fl = np.where(np.abs(r.x) < 1e-9, 0.0, r.x); out['distribution'] = {'status': 'optimal', 'total_cost': float(r.fun), 'flows': [{'from': e['from'], 'to': e['to'], 'flow': float(fl[j])} for j, e in enumerate(E) if fl[j] > 1e-9]}
            summ.append(f'Оптимальное распределение поставок: суммарные затраты на перевозку {fnum(r.fun, 1)}; задействовано {len(out["distribution"]["flows"])} связей.')
            tables['distribution'] = table(['Откуда', 'Куда', 'Объём'], [[f['from'], f['to'], f['flow']] for f in out['distribution']['flows']], 'Оптимальные потоки')
    deg = {nd: {'in': sum(1 for e in E if e['to'] == nd), 'out': sum(1 for e in E if e['from'] == nd)} for nd in nodes}
    if all('capacity' in e for e in E):
        for nd in nodes: deg[nd]['in_capacity'] = sum(e['capacity'] for e in E if e['to'] == nd); deg[nd]['out_capacity'] = sum(e['capacity'] for e in E if e['from'] == nd)
    out['nodes'] = deg
    tables['nodes'] = table(['Узел', 'Входящих связей', 'Исходящих связей'], [[nd, d['in'], d['out']] for nd, d in deg.items()], 'Транспортные узлы')
    ch = tables.get('flows')
    chart = {'type': 'bar', 'title': 'Загрузка связей, %', 'labels': [f'{r[0]}→{r[1]}' for r in ch['rows']], 'values': [r[4] for r in ch['rows']]} if ch else None
    out.update({'summary_ru': summ, 'warnings': warns, 'tables': tables, 'chart': chart})
    return out

# ---------------------------------------------------------------- M14
def m14_scenarios(records, scenarios=None, sensitivity_pct=10.0, series=None, confidence=0.95, factor_labels=None):
    """records — статьи результата: {name, type: revenue|cost, amount, factor, pass_through(=1)}.
    Сценарии задают допущения {name, shocks:{factor: % изменения}, stress(необязательно), assumptions}.
    Результат — «что будет, если допущения верны», а не прогноз."""
    items = []
    for i, r in enumerate(records):
        if r.get('type') not in ('revenue', 'cost'): raise ValueError(f'Статья {i}: type должен быть revenue или cost')
        items.append({'name': str(r['name']), 'type': r['type'], 'amount': num(r['amount'], 'amount'), 'factor': r.get('factor'), 'pt': num(r.get('pass_through', 1.0), 'pass_through')})
    if not items: raise ValueError('Нет статей')
    def result(shocks):
        tot = 0.; det = []
        for it in items:
            sh = shocks.get(it['factor'], 0.0) if it['factor'] else 0.0
            new = it['amount'] * (1 + it['pt'] * sh / 100); det.append({'name': it['name'], 'type': it['type'], 'base': it['amount'], 'new': new})
            tot += new if it['type'] == 'revenue' else -new
        return tot, det
    lab = lambda f: (factor_labels or {}).get(f, f)
    base, _ = result({}); factors = sorted({it['factor'] for it in items if it['factor']})
    out = {'base_result': base}; summ = [f'Базовый результат (выручка − затраты): {fnum(base, 1)}.']; warns = ['Сценарии — допущения пользователя, а не прогноз. Реакция статей на факторы (pass_through) задана вручную и должна быть обоснована.']
    sens = []
    for f in factors:
        up, _ = result({f: sensitivity_pct}); dn, _ = result({f: -sensitivity_pct}); sens.append({'factor': f, 'if_up': up - base, 'if_down': dn - base, 'swing': abs(up - dn)})
    sens.sort(key=lambda s: -s['swing']); out['sensitivity'] = sens
    if sens:
        s0 = sens[0]; summ.append(f'Сильнее всего на результат влияет «{lab(s0["factor"])}»: рост на {fnum(sensitivity_pct, 0)} % меняет результат на {fnum(s0["if_up"], 1)}, падение на {fnum(sensitivity_pct, 0)} % — на {fnum(s0["if_down"], 1)}.')
    sc_out = []
    for sc in scenarios or []:
        r, det = result(sc.get('shocks', {})); unk = [k for k in sc.get('shocks', {}) if k not in factors]
        if unk: warns.append(f'Сценарий «{sc["name"]}»: факторы {", ".join(lab(u) for u in unk)} не связаны ни с одной статьёй и не влияют на результат.')
        d = r - base; word = 'меньше' if d < 0 else 'больше'; sc_out.append({'name': sc['name'], 'stress': bool(sc.get('stress')), 'assumptions': sc.get('assumptions', ''), 'shocks': sc.get('shocks', {}), 'result': r, 'change': d, 'change_pct': (d / abs(base) * 100) if base else None, 'items': det})
        summ.append(f'Сценарий «{sc["name"]}»{" (стресс)" if sc.get("stress") else ""}: результат {fnum(r, 1)}, это на {fnum(abs(d), 1)} ({fnum(abs(sc_out[-1]["change_pct"]), 0) + " %" if sc_out[-1]["change_pct"] is not None else "—"}) {word} базы.' + (f' Допущения: {sc["assumptions"]}.' if sc.get('assumptions') else ''))
    out['scenarios'] = sc_out
    if series:
        x = np.array([num(v, 'series') for v in series]); q = float(np.quantile(x, confidence)); tail = x[x >= q]
        out['historical'] = {'mean': float(x.mean()), 'sd': float(x.std(ddof=1)), 'quantile': q, 'expected_shortfall': float(tail.mean()), 'n': len(x), 'confidence': confidence}
        summ.append(f'По истории ({len(x)} наблюдений): {pct(confidence * 100, 0)}-я граница потерь {fnum(q, 2)}, средние потери в худших случаях {fnum(tail.mean(), 2)}. Редкие события история может не содержать.')
    tables = {'sensitivity': table(['Фактор', f'+{fnum(sensitivity_pct, 0)} %', f'−{fnum(sensitivity_pct, 0)} %', 'Размах'], [[lab(s['factor']), s['if_up'], s['if_down'], s['swing']] for s in sens], 'Чувствительность результата')}
    if sc_out: tables['scenarios'] = table(['Сценарий', 'Результат', 'Изменение', 'Изменение, %', 'Стресс'], [[s['name'], s['result'], s['change'], s['change_pct'], 'да' if s['stress'] else ''] for s in sc_out], 'Сценарии')
    chart = {'type': 'bar', 'title': 'Изменение результата по сценариям', 'labels': [s['name'] for s in sc_out], 'values': [s['change'] for s in sc_out]} if sc_out else None
    out.update({'summary_ru': summ, 'warnings': warns, 'tables': tables, 'chart': chart})
    return out
