"""Модули по спецификации: M05 себестоимость, M06 межотраслевой анализ, M08 причинный анализ, M10 оптимизация."""
from __future__ import annotations
import math
import numpy as np
from scipy.optimize import linprog, milp, LinearConstraint, Bounds
from scipy.stats import norm
from economia_spec_common import fnum, pct, num, sorted_rows, table

KIND_RU = {'accounting': 'бухгалтерский показатель', 'economic': 'экономическая оценка', 'estimate': 'расчётное приближение'}
DEFAULT_ITEMS = {'materials': 'Материалы', 'energy': 'Энергия', 'labour': 'Оплата труда', 'depreciation': 'Амортизация', 'other': 'Прочие затраты'}


# ------------------------------------------------------------------ M05
def m05_cost_analysis(records, period='period', group=None, output='output', items=None, kinds=None):
    """Себестоимость: структура затрат, затраты на единицу, факторы изменения между первым и последним периодом, сравнение групп.
    records: {period, [group], output, materials, energy, labour, depreciation, other}. Колонки задаются словарём items {колонка: название}.
    kinds: {колонка: accounting|economic|estimate}; по умолчанию все «бухгалтерские»."""
    items = dict(items or {k: v for k, v in DEFAULT_ITEMS.items() if any(k in r for r in records)})
    if not items: raise ValueError('Не найдено ни одной статьи затрат: задайте items')
    kinds = {k: (kinds or {}).get(k, 'accounting') for k in items}
    bad = [k for k, v in kinds.items() if v not in KIND_RU]
    if bad: raise ValueError(f'Недопустимый тип показателя у {bad}: нужно accounting, economic или estimate')
    rows = []
    for r in records:
        q = num(r[output], output)
        if q <= 0: raise ValueError(f'Выпуск должен быть положительным (период {r[period]})')
        c = {k: num(r[k], k) for k in items}
        if any(v < 0 for v in c.values()): raise ValueError(f'Затраты не могут быть отрицательными (период {r[period]})')
        rows.append({'g': str(r[group]) if group else 'Всего', 'p': str(r[period]), 'q': q, 'c': c, 'tot': sum(c.values())})
    groups = list(dict.fromkeys(r['g'] for r in rows))
    out = {'groups': {}}; summ = []; warns = []; tabs = {}
    if any(v != 'accounting' for v in kinds.values()):
        warns.append('Показатели разного типа: ' + '; '.join(f'«{items[k]}» — {KIND_RU[v]}' for k, v in kinds.items() if v != 'accounting') + '. Не смешивайте их с бухгалтерскими данными без оговорки.')
    last_rows = []; chart = None
    for g in groups:
        rs = sorted_rows([r for r in rows if r['g'] == g], 'p'); a, b = rs[0], rs[-1]
        share = {k: b['c'][k] / b['tot'] if b['tot'] else None for k in items}
        unit = {k: b['c'][k] / b['q'] for k in items}; uc_b, uc_a = b['tot'] / b['q'], a['tot'] / a['q']
        info = {'first': a['p'], 'last': b['p'], 'unit_cost_first': uc_a, 'unit_cost_last': uc_b, 'shares_last': share, 'unit_items_last': unit}
        if len(rs) >= 2:
            contrib = {k: b['c'][k] / b['q'] - a['c'][k] / a['q'] for k in items}
            vol = (b['q'] - a['q']) * uc_a; unit_eff = b['q'] * (uc_b - uc_a)
            info.update({'unit_cost_change': uc_b - uc_a, 'contrib': contrib, 'total_cost_change': b['tot'] - a['tot'], 'volume_effect': vol, 'unit_cost_effect': unit_eff})
            top = max(contrib, key=lambda k: abs(contrib[k]))
            summ.append(f'{"«" + g + "»: " if group else ""}себестоимость единицы {a["p"]} → {b["p"]}: {fnum(uc_a, 2)} → {fnum(uc_b, 2)} ({pct((uc_b / uc_a - 1) * 100, 1)}); сильнее всего на это повлияла статья «{items[top]}» ({"+" if contrib[top] >= 0 else "−"}{fnum(abs(contrib[top]), 2)} на единицу).')
            if group is None or g == groups[0]:
                chart = {'type': 'bar', 'title': f'Вклад статей в изменение себестоимости единицы ({a["p"]} → {b["p"]})' + (f', {g}' if group else ''), 'labels': [items[k] for k in items], 'values': [contrib[k] for k in items]}
        else:
            summ.append(f'{"«" + g + "»: " if group else ""}себестоимость единицы за {b["p"]}: {fnum(uc_b, 2)}; один период — динамику посчитать нельзя.')
        big = max(share, key=lambda k: share[k] or 0)
        summ.append(f'{"«" + g + "»: " if group else ""}крупнейшая статья на {b["p"]}: «{items[big]}» ({pct(share[big] * 100, 1)} затрат).')
        out['groups'][g] = info; last_rows.append([g, b['p'], b['q'], b['tot'], uc_b] + [share[k] * 100 if share[k] is not None else None for k in items])
    tabs['structure'] = table(['Группа', 'Период', 'Выпуск', 'Затраты', 'На единицу'] + [f'{items[k]}, %' for k in items], last_rows, 'Структура себестоимости (последний период)')
    if any('contrib' in v for v in out['groups'].values()):
        tabs['factors'] = table(['Группа', 'Статья', 'Изменение на единицу'], [[g, items[k], v['contrib'][k]] for g, v in out['groups'].items() if 'contrib' in v for k in items], 'Факторы изменения себестоимости единицы')
        tabs['effects'] = table(['Группа', 'Изменение затрат', 'Эффект выпуска', 'Эффект себестоимости'], [[g, v['total_cost_change'], v['volume_effect'], v['unit_cost_effect']] for g, v in out['groups'].items() if 'contrib' in v], 'Рост затрат: за счёт объёма и за счёт себестоимости')
    if len(groups) > 1:
        cheapest = min(out['groups'], key=lambda g: out['groups'][g]['unit_cost_last']); dearest = max(out['groups'], key=lambda g: out['groups'][g]['unit_cost_last'])
        summ.append(f'Сравнение: дешевле всего единица у «{cheapest}» ({fnum(out["groups"][cheapest]["unit_cost_last"], 2)}), дороже всего у «{dearest}» ({fnum(out["groups"][dearest]["unit_cost_last"], 2)}).')
    warns.append('Различия в себестоимости показывают, где расходы выше, но не объясняют причины без данных о ценах ресурсов и технологиях.')
    out.update({'summary_ru': summ, 'warnings': warns, 'tables': tabs, 'chart': chart, 'kinds': {items[k]: KIND_RU[v] for k, v in kinds.items()}})
    return out


# ------------------------------------------------------------------ M06
def m06_input_output(records, demand_change=None, tol=1e-6):
    """Модель «затраты — выпуск» Леонтьева. records[0]: industry_ids, Z (межотраслевые потоки, Z[i][j] — из i в j),
    gross_output x, domestic_final_demand y; необязательно: intermediate_imports (по отраслям-потребителям), value_added.
    demand_change: {отрасль: изменение конечного спроса} -> эффект на выпуск (Δx = (I−A)⁻¹Δy)."""
    cfg = records[0]; ids = [str(i) for i in cfg['industry_ids']]; n = len(ids)
    Z = np.asarray(cfg['Z'], float); x = np.asarray(cfg['gross_output'], float); y = np.asarray(cfg['domestic_final_demand'], float)
    if len(set(ids)) != n: raise ValueError('Повторяются коды отраслей')
    if Z.shape != (n, n) or x.shape != (n,) or y.shape != (n,): raise ValueError('Размеры Z, выпуска и конечного спроса не согласованы')
    if not (np.isfinite(Z).all() and np.isfinite(x).all() and np.isfinite(y).all()): raise ValueError('Матрицы содержат нечисловые значения')
    if (Z < 0).any() or (x <= 0).any() or (y < 0).any(): raise ValueError('Потоки и конечный спрос не могут быть отрицательными, выпуск должен быть положительным')
    A = Z / x[np.newaxis, :]
    rho = float(max(abs(np.linalg.eigvals(A))))
    if rho >= 1: raise ValueError(f'Система непродуктивна: спектральный радиус A равен {rho:.4f} ≥ 1')
    L = np.linalg.inv(np.eye(n) - A); xm = L @ y
    resid = float(np.max(np.abs(xm - x) / x)); checks = []; warns = []
    row_gap = x - Z.sum(axis=1) - y
    checks.append(('Баланс по строкам: выпуск = продажи отраслям + конечный спрос', float(np.max(np.abs(row_gap) / x)), float(np.max(np.abs(row_gap) / x)) <= 1e-3))
    checks.append(('Согласованность x = (I − A)⁻¹y с заданным выпуском', resid, resid <= 1e-3))
    imp = cfg.get('intermediate_imports'); va = cfg.get('value_added')
    if imp is not None:
        imp = np.asarray(imp, float)
        if imp.shape != (n,) or (imp < 0).any(): raise ValueError('intermediate_imports: нужен неотрицательный вектор по отраслям')
    if imp is not None and va is not None:
        va = np.asarray(va, float); colgap = x - Z.sum(axis=0) - imp - va
        checks.append(('Баланс по столбцам: выпуск = затраты отраслей + импорт + добавленная стоимость', float(np.max(np.abs(colgap) / x)), float(np.max(np.abs(colgap) / x)) <= 1e-3))
    if not all(c[2] for c in checks): warns.append('Проверка баланса не пройдена: таблица несогласована (допуск 0,1 %). Расчёт выполнен, но по несогласованной таблице выводам верить нельзя.')
    mult = L.sum(axis=0); fwd = L.sum(axis=1)
    back = mult / mult.mean(); forw = fwd / fwd.mean()
    out = {'industry_ids': ids, 'A': A.tolist(), 'leontief_inverse': L.tolist(), 'calculated_output': xm.tolist(), 'rho_A': rho, 'condition_number': float(np.linalg.cond(np.eye(n) - A)),
           'output_multipliers': mult.tolist(), 'backward_linkage': back.tolist(), 'forward_linkage': forw.tolist(), 'balance_checks': [{'name': c[0], 'max_rel_gap': c[1], 'ok': c[2]} for c in checks]}
    summ = [f'Отраслей: {n}. Матрица A построена, система продуктивна (спектральный радиус {fnum(rho, 3)}).']
    k = int(np.argmax(mult)); summ.append(f'Наибольший мультипликатор выпуска у отрасли «{ids[k]}»: рост её конечного спроса на 1 даёт рост выпуска всей экономики на {fnum(mult[k], 2)}.')
    tabs = {'industries': table(['Отрасль', 'Валовой выпуск', 'Конечный спрос', 'Мультипликатор выпуска', 'Связь «назад»', 'Связь «вперёд»'] + (['Доля импорта в затратах, %'] if imp is not None else []),
            [[ids[i], float(x[i]), float(y[i]), float(mult[i]), float(back[i]), float(forw[i])] + ([float(imp[i] / x[i] * 100)] if imp is not None else []) for i in range(n)], 'Отрасли и их взаимосвязи')}
    if imp is not None:
        out['import_share'] = (imp / x).tolist(); tot = float(imp.sum()); summ.append(f'Импортная составляющая: {fnum(tot, 1)} ({pct(tot / float(x.sum()) * 100, 1)} валового выпуска).')
    tabs['checks'] = table(['Проверка', 'Макс. относительное расхождение', 'Результат'], [[c[0], c[1] * 100, 'пройдена' if c[2] else 'НЕ пройдена'] for c in checks], 'Проверка матриц и балансов (расхождение в %)')
    if demand_change:
        unk = [i for i in demand_change if str(i) not in ids]
        if unk: raise ValueError(f'Неизвестные отрасли в demand_change: {unk}')
        dy = np.zeros(n)
        for i, v in demand_change.items(): dy[ids.index(str(i))] = num(v, 'demand_change')
        dx = L @ dy; out['demand_change'] = {'delta_y': dy.tolist(), 'delta_x': dx.tolist()}
        summ.append('Эффект изменения конечного спроса: ' + '; '.join(f'«{i}» {"+" if v >= 0 else "−"}{fnum(abs(v), 1)}' for i, v in demand_change.items()) + f' → общий прирост выпуска {fnum(float(dx.sum()), 1)} (из них прямо в этих отраслях {fnum(float(dy.sum()), 1)}).')
        tabs['effect'] = table(['Отрасль', 'Изменение конечного спроса', 'Изменение выпуска'], [[ids[i], float(dy[i]), float(dx[i])] for i in range(n)], 'Влияние изменения конечного спроса')
    warns.append('Коэффициенты A считаются по одному году и предполагают фиксированную технологию; результат — «что будет, если структура затрат не изменится», а не прогноз.')
    out.update({'summary_ru': summ, 'warnings': warns, 'tables': tabs, 'chart': {'type': 'bar', 'title': 'Мультипликаторы выпуска по отраслям', 'labels': ids, 'values': mult.tolist()}})
    return out


# ------------------------------------------------------------------ M08
def _cluster_ols(X, y, cl=None):
    n, k = X.shape; XtXi = np.linalg.inv(X.T @ X); b = XtXi @ X.T @ y; u = y - X @ b
    if cl is None:
        V = XtXi @ ((X * u[:, None]).T @ (X * u[:, None])) @ XtXi * n / max(n - k, 1); G = None
    else:
        ug = np.unique(cl); G = len(ug); meat = np.zeros((k, k))
        for g in ug: s = X[cl == g].T @ u[cl == g]; meat += np.outer(s, s)
        V = XtXi @ meat @ XtXi * (G / (G - 1)) * ((n - 1) / max(n - k, 1))
    return b, np.sqrt(np.maximum(np.diag(V), 0)), G


def m08_causal_analysis(records, outcome='outcome', treated='treated', post='post', period=None, unit=None, controls=(), cluster=None):
    """Разность разностей (DiD): сравнение групп, до/после, эффект воздействия, контрольные переменные, проверки предпосылок и устойчивости.
    records: {outcome, treated 0/1, post 0/1, [period], [unit], [контрольные]}. cluster — поле для кластерных ошибок (обычно unit)."""
    ctrl = list(controls); n = len(records)
    y = np.array([num(r[outcome], outcome) for r in records]); t = np.array([num(r[treated], treated) for r in records]); p = np.array([num(r[post], post) for r in records])
    if not (set(np.unique(t)) <= {0., 1.} and set(np.unique(p)) <= {0., 1.}): raise ValueError('treated и post должны быть 0/1')
    cells = {(a, b): y[(t == a) & (p == b)] for a in (0., 1.) for b in (0., 1.)}
    if any(len(v) == 0 for v in cells.values()): raise ValueError('Нужны наблюдения во всех четырёх группах: воздействие/контроль × до/после')
    mean = {k: float(v.mean()) for k, v in cells.items()}
    did = (mean[(1., 1.)] - mean[(1., 0.)]) - (mean[(0., 1.)] - mean[(0., 0.)])
    cl = np.array([str(r[cluster]) for r in records]) if cluster else None
    if cl is not None and len(np.unique(cl)) < 2: raise ValueError('Для кластерных ошибок нужно не менее двух кластеров')
    base = [np.ones(n), t, p, t * p]
    def fit(extra, clu):
        X = np.column_stack(base + extra); b, se, G = _cluster_ols(X, y, clu); return float(b[3]), float(se[3]), G
    Cm = [np.array([num(r[c], c) for r in records]) for c in ctrl]
    e0, s0, G = fit([], cl); e1, s1, _ = fit(Cm, cl) if Cm else (e0, s0, G)
    z = e1 / s1 if s1 > 0 else float('nan'); pv = 2 * (1 - norm.cdf(abs(z))) if s1 > 0 else float('nan')
    out = {'n': n, 'cell_means': {f'treated={int(a)},post={int(b)}': v for (a, b), v in mean.items()}, 'did_simple': did, 'effect': e1, 'standard_error': s1, 'p_value_normal_approx': pv,
           'ci95': [e1 - 1.96 * s1, e1 + 1.96 * s1], 'with_controls': bool(Cm), 'effect_without_controls': e0, 'clusters': G}
    summ = [f'Группа воздействия: до {fnum(mean[(1., 0.)], 2)}, после {fnum(mean[(1., 1.)], 2)}. Контрольная группа: до {fnum(mean[(0., 0.)], 2)}, после {fnum(mean[(0., 1.)], 2)}.',
            f'Оценка эффекта воздействия (разность разностей): {fnum(e1, 3)} (95 % интервал {fnum(e1 - 1.96 * s1, 3)} … {fnum(e1 + 1.96 * s1, 3)}).']
    warns = ['Статистическая связь сама по себе не доказывает причинность: оценка верна только если до воздействия группы развивались параллельно и ничто другое не изменилось одновременно с воздействием.']
    if s1 > 0 and abs(z) < 1.96: summ.append('Эффект статистически неотличим от нуля: интервал включает 0.')
    if G is not None and G < 30: warns.append(f'Мало кластеров ({G}): кластерные ошибки и нормальный интервал могут быть слишком оптимистичными.')
    checks = []; tabs = {}
    # устойчивость: контрольные переменные
    if Cm:
        checks.append(['Эффект без контрольных переменных', e0, 'устойчивость']); shift = abs(e1 - e0) / abs(e0) if e0 else None
        if shift is not None and shift > 0.25: warns.append(f'Контрольные переменные заметно меняют оценку (на {pct(shift * 100, 0)}): результат неустойчив к спецификации.')
    # предпосылка параллельных трендов и плацебо
    if period is not None:
        per = np.array([num(r[period], period) for r in records]); pre = p == 0
        if len(np.unique(per[pre])) >= 3:
            Xp = np.column_stack([np.ones(pre.sum()), t[pre], per[pre], t[pre] * per[pre]]); bp, sep, _ = _cluster_ols(Xp, y[pre], cl[pre] if cl is not None else None)
            zt = bp[3] / sep[3] if sep[3] > 0 else float('nan'); out['pretrend'] = {'slope_difference': float(bp[3]), 'se': float(sep[3])}
            checks.append(['Разница трендов до воздействия (должна быть около 0)', float(bp[3]), f'z = {fnum(zt, 2)}'])
            if sep[3] > 0 and abs(zt) >= 1.96: warns.append('До воздействия группы развивались непараллельно (разница трендов значима): предпосылка DiD сомнительна.')
            pu = np.unique(per[pre]); cut = pu[len(pu) // 2]; fake = (per >= cut).astype(float)
            Xf = np.column_stack([np.ones(pre.sum()), t[pre], fake[pre], t[pre] * fake[pre]]); bf, sef, _ = _cluster_ols(Xf, y[pre], cl[pre] if cl is not None else None)
            zf = bf[3] / sef[3] if sef[3] > 0 else float('nan'); out['placebo'] = {'effect': float(bf[3]), 'se': float(sef[3])}
            checks.append(['Плацебо: «эффект» в периоде до реального воздействия (должен быть около 0)', float(bf[3]), f'z = {fnum(zf, 2)}'])
            if sef[3] > 0 and abs(zf) >= 1.96: warns.append('Плацебо-проверка показала «эффект» там, где воздействия не было: оценка может отражать иные причины.')
        else: warns.append('Параллельность трендов не проверена: до воздействия меньше трёх периодов.')
    else: warns.append('Параллельность трендов не проверена: не указано поле периода (period).')
    tabs['cells'] = table(['Группа', 'До', 'После', 'Изменение'], [['Воздействие', mean[(1., 0.)], mean[(1., 1.)], mean[(1., 1.)] - mean[(1., 0.)]], ['Контроль', mean[(0., 0.)], mean[(0., 1.)], mean[(0., 1.)] - mean[(0., 0.)]], ['Разность разностей', None, None, did]], 'Сравнение групп до и после')
    if checks: tabs['checks'] = table(['Проверка', 'Значение', 'Заключение'], checks, 'Диагностика предпосылок и устойчивости')
    out.update({'summary_ru': summ, 'warnings': warns, 'tables': tabs, 'chart': {'type': 'bar', 'title': 'Изменение «после − до»', 'labels': ['Воздействие', 'Контроль', 'Разность разностей'], 'values': [mean[(1., 1.)] - mean[(1., 0.)], mean[(0., 1.)] - mean[(0., 0.)], did]}})
    return out


# ------------------------------------------------------------------ M10
def m10_production_optimisation(records, objective='max_profit', integer=False, secondary=None, pareto_points=5):
    """records[0]: {products:[{name, profit|cost, uses:{ресурс: расход на единицу}, min, max}], resources:{ресурс: мощность}, [min_total_output]}.
    objective: max_profit (максимум прибыли) | min_cost (минимум затрат при выпуске не ниже min у продуктов).
    integer=True — целочисленные объёмы. secondary={'name','coef':{продукт: значение},'sense':'min'|'max'} — второй критерий:
    строится набор компромиссных решений (метод ограничений). Теневые цены берутся из линейной релаксации."""
    cfg = records[0]; prods = cfg['products']; res = cfg['resources']; n = len(prods); rn = list(res)
    if n == 0 or not rn: raise ValueError('Нужны продукты и ресурсы')
    if objective not in ('max_profit', 'min_cost'): raise ValueError('objective: max_profit или min_cost')
    names = [str(p['name']) for p in prods]
    if len(set(names)) != n: raise ValueError('Повторяются названия продуктов')
    key = 'profit' if objective == 'max_profit' else 'cost'
    c = np.array([num(p[key], key) for p in prods])
    A = np.array([[num((p.get('uses') or {}).get(r, 0.0), r) for p in prods] for r in rn]); b = np.array([num(res[r], r) for r in rn])
    if (A < 0).any() or (b < 0).any(): raise ValueError('Расход и мощности ресурсов не могут быть отрицательными')
    lo = np.array([num(p.get('min', 0.0), 'min') for p in prods]); hi = np.array([num(p['max'], 'max') if p.get('max') is not None else np.inf for p in prods])
    if (lo > hi).any(): raise ValueError('У продукта минимум больше максимума')
    if objective == 'min_cost' and (lo <= 0).all(): raise ValueError('Для минимизации затрат задайте минимальные объёмы (min) продуктов: иначе оптимум — ничего не производить')
    def solve(cc, extra=None, integ=integer):
        Aub, bub = A, b
        if extra is not None: Aub = np.vstack([A, extra[0]]); bub = np.concatenate([b, [extra[1]]])
        sgn = -1.0 if objective == 'max_profit' else 1.0
        if integ:
            r = milp(sgn * cc, constraints=LinearConstraint(Aub, -np.inf, bub), integrality=np.ones(n), bounds=Bounds(lo, hi))
            return (r.x if r.success else None), r
        r = linprog(sgn * cc, A_ub=Aub, b_ub=bub, bounds=list(zip(lo, hi)), method='highs')
        return (r.x if r.success else None), r
    x, r = solve(c)
    if x is None: return {'optimal': False, 'status': 'INFEASIBLE', 'summary_ru': ['Допустимого плана нет: ограничения противоречат друг другу (например, минимальные объёмы требуют больше ресурсов, чем есть).'], 'warnings': [], 'tables': {}, 'chart': None}
    x = np.round(x, 9) if integer else np.where(np.abs(x) < 1e-9, 0.0, x)
    val = float(c @ x); use = A @ x; util = np.where(b > 0, use / np.where(b > 0, b, 1) * 100, 0.0)
    lp = linprog((-1.0 if objective == 'max_profit' else 1.0) * c, A_ub=A, b_ub=b, bounds=list(zip(lo, hi)), method='highs')
    duals = (-lp.ineqlin.marginals if objective == 'max_profit' else lp.ineqlin.marginals) if lp.success else np.zeros(len(rn))
    duals = np.where(np.abs(duals) < 1e-9, 0.0, duals)
    binding = [rn[i] for i in range(len(rn)) if b[i] > 0 and use[i] >= b[i] * (1 - 1e-7)]
    word = 'прибыль' if objective == 'max_profit' else 'затраты'
    summ = [f'{"Целочисленный" if integer else "Оптимальный"} план: {word} {fnum(val, 2)}.', 'Объёмы: ' + '; '.join(f'{names[i]} — {fnum(float(x[i]), 2 if not integer else 0)}' for i in range(n)) + '.']
    summ.append('Узкие места (ресурс используется полностью): ' + (', '.join(binding) if binding else 'нет') + '.')
    if binding and objective == 'max_profit':
        top = max(binding, key=lambda r_: duals[rn.index(r_)])
        summ.append(f'Ещё одна единица ресурса «{top}» увеличила бы прибыль примерно на {fnum(float(duals[rn.index(top)]), 2)} (теневая цена, для небольшого изменения).')
    warns = []
    if integer: warns.append('Теневые цены посчитаны для линейной релаксации (без целочисленности) и только ориентировочны.')
    if (np.isinf(hi)).all() and objective == 'max_profit': warns.append('Верхние границы объёмов не заданы: убедитесь, что спроса на такой выпуск хватает.')
    out = {'optimal': True, 'objective_value': val, 'plan': dict(zip(names, map(float, x))), 'resource_use': dict(zip(rn, map(float, use))), 'utilisation_pct': dict(zip(rn, map(float, util))), 'shadow_prices': dict(zip(rn, map(float, duals))), 'binding': binding, 'integer': bool(integer)}
    tabs = {'plan': table(['Продукт', 'Объём', 'Удельный ' + ('доход' if objective == 'max_profit' else 'затраты'), 'Вклад'], [[names[i], float(x[i]), float(c[i]), float(c[i] * x[i])] for i in range(n)], 'План производства'),
            'resources': table(['Ресурс', 'Нужно', 'Мощность', 'Загрузка, %', 'Теневая цена'], [[rn[i], float(use[i]), float(b[i]), float(util[i]), float(duals[i])] for i in range(len(rn))], 'Ресурсы, загрузка мощностей и теневые цены')}
    if secondary:
        sc = np.array([num((secondary.get('coef') or {}).get(nm, 0.0), 'coef') for nm in names]); minimise = secondary.get('sense', 'min') == 'min'; sname = secondary.get('name', 'Второй критерий')
        # границы: оптимум по основному и по второму критерию
        pts = []
        s_main = float(sc @ x)
        lo_b = linprog(sc, A_ub=A, b_ub=b, bounds=list(zip(lo, hi)), method='highs'); hi_b = linprog(-sc, A_ub=A, b_ub=b, bounds=list(zip(lo, hi)), method='highs')
        if lo_b.success and hi_b.success:
            lo_s, hi_s = float(sc @ lo_b.x), float(sc @ hi_b.x)
            targets = np.linspace(lo_s, hi_s, max(pareto_points, 2))
            for tgt in targets:
                row = (sc, tgt) if minimise else (-sc, -tgt)           # sc·x ≤ tgt (минимизируем) или sc·x ≥ tgt
                xx, _ = solve(c, extra=row, integ=integer)
                if xx is not None: pts.append([float(c @ xx), float(sc @ xx)])
            seen = []
            for p_ in pts:
                if not any(abs(p_[0] - q_[0]) < 1e-9 and abs(p_[1] - q_[1]) < 1e-9 for q_ in seen): seen.append(p_)
            out['pareto'] = seen
            if seen:
                tabs['pareto'] = table([word.capitalize(), sname], seen, f'Компромисс между критериями: {word} и «{sname}»')
                summ.append(f'Второй критерий «{sname}» в оптимальном плане: {fnum(s_main, 2)}. Компромиссные планы (чем лучше второй критерий, тем хуже основной) — в таблице «Компромисс».')
    out.update({'summary_ru': summ, 'warnings': warns, 'tables': tabs, 'chart': {'type': 'bar', 'title': 'Загрузка ресурсов, %', 'labels': rn, 'values': [float(u) for u in util]}})
    return out
