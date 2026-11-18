"""Модули по спецификации: M02 спрос и активность, M03 цены, M04 производительность,
M07 макроанализ, M11 несколько рынков. Каждый результат содержит summary_ru (простым языком),
таблицы и, где уместно, график. Прежние методы доступны через параметр method в economia_modules."""
from __future__ import annotations
import math
import numpy as np
from economia_spec_common import fnum, pct, num, sorted_rows, require_complete, pos_label, ols, table

# ---------------------------------------------------------------- M02
def m02_demand_activity(records, value='value', period='period', price=None, others=(), season_length=12):
    rows = sorted_rows(records, period); n = len(rows)
    if n < 3: raise ValueError('Нужно не менее 3 периодов')
    per = [str(r[period]) for r in rows]; require_complete(per, 'оборот/продажи')
    y = np.array([num(r[value], value) for r in rows]); m = int(season_length)
    mom = [None] + [((y[i] / y[i - 1] - 1) * 100) if y[i - 1] != 0 else None for i in range(1, n)]
    yoy = [None] * min(m, n) + [((y[i] / y[i - m] - 1) * 100) if y[i - m] != 0 else None for i in range(m, n)] if m >= 1 else [None] * n
    trend = [None] * n; seas = [None] * n; season = None
    warns = []
    if m >= 2 and n >= 2 * m:
        w = np.r_[0.5, np.ones(m - 1), 0.5] / m if m % 2 == 0 else np.ones(m) / m
        half = len(w) // 2
        for i in range(half, n - half): trend[i] = float(np.dot(w, y[i - half:i + half + 1]))
        det = [(i, y[i] - trend[i]) for i in range(n) if trend[i] is not None]
        idx = np.zeros(m); cnt = np.zeros(m)
        for i, d in det: idx[i % m] += d; cnt[i % m] += 1
        idx = idx / np.maximum(cnt, 1); idx -= idx.mean()
        for i in range(n): seas[i] = float(idx[i % m])
        rem = np.array([y[i] - trend[i] - seas[i] for i, _ in det]); sr = np.array([y[i] - trend[i] for i, _ in det])
        strength = max(0.0, 1 - float(np.var(rem)) / float(np.var(sr))) if np.var(sr) > 0 else 0.0
        labels = [pos_label(per[k], m) or f'позиция {k + 1}' for k in range(m)]
        season = {'indices': {labels[k]: float(idx[(k)]) for k in range(m)}, 'strength': strength,
                  'peak': labels[int(np.argmax(idx))], 'trough': labels[int(np.argmin(idx))]}
    elif m >= 2: warns.append(f'Для оценки сезонности нужно минимум {2 * m} периодов, есть {n}: сезонность не оценивалась.')
    out = {'n': n, 'last_period': per[-1], 'last_value': float(y[-1]), 'last_mom_pct': mom[-1], 'last_yoy_pct': yoy[-1] if len(yoy) == n else None,
           'seasonality': season, 'warnings': warns}
    summ = [f'Последний период ({per[-1]}): {fnum(y[-1])}.']
    if mom[-1] is not None: summ.append(f'К предыдущему периоду: {pct(mom[-1])}.')
    if out['last_yoy_pct'] is not None: summ.append(f'К тому же периоду год назад: {pct(out["last_yoy_pct"])}.')
    if season:
        s = season['strength']
        word = 'выраженная' if s > 0.6 else 'умеренная' if s > 0.3 else 'слабая'
        summ.append(f'Сезонность {word} (сила {fnum(s, 2)} из 1). Пик: {season["peak"]}, спад: {season["trough"]}.')
    if price:
        pr = np.array([num(r[price], price) for r in rows])
        if (y <= 0).any() or (pr <= 0).any(): warns.append('Чувствительность к цене не оценивалась: нужны положительные значения оборота и цены.')
        else:
            b, se, r2 = ols(np.column_stack([np.ones(n), np.log(pr)]), np.log(y))
            out['price_sensitivity'] = {'elasticity': float(b[1]), 'se': float(se[1]), 'ci95': [float(b[1] - 1.96 * se[1]), float(b[1] + 1.96 * se[1])], 'r2': r2, 'n': n}
            summ.append(f'Чувствительность оборота к цене: {fnum(b[1], 2)} (95 % интервал {fnum(b[1] - 1.96 * se[1], 2)} … {fnum(b[1] + 1.96 * se[1], 2)}). Это наблюдаемая связь, а не доказанное причинное влияние.')
    corr = []
    for name in others or ():
        z = np.array([num(r[name], name) for r in rows])
        if np.std(np.diff(y)) > 0 and np.std(np.diff(z)) > 0:
            corr.append({'indicator': name, 'corr_of_changes': float(np.corrcoef(np.diff(y), np.diff(z))[0, 1]), 'n': n - 1})
    if corr:
        out['correlations'] = corr
        summ += [f'Связь изменений с «{c["indicator"]}»: {fnum(c["corr_of_changes"], 2)}. Корреляция не доказывает причинность.' for c in corr]
    out['summary_ru'] = summ
    out['tables'] = {'series': table(['Период', 'Значение', 'К пред. периоду, %', 'К году назад, %', 'Тренд', 'Сезонная добавка'],
        [[per[i], float(y[i]), mom[i], yoy[i] if len(yoy) == n else None, trend[i], seas[i]] for i in range(n)], 'Динамика и сезонность')}
    out['chart'] = {'type': 'line', 'title': 'Значение и тренд', 'x': per, 'series': [{'name': 'Значение', 'values': [float(v) for v in y]}, {'name': 'Тренд', 'values': trend, 'dash': True}]}
    out['warnings'] = warns
    return out

# ---------------------------------------------------------------- M03
def m03_price_analysis(records, price='price', period='period', group=None, base_period=None, season_length=12, nominal=None, deflator=None):
    """Цена товара, индекс цен и стоимость корзины — разные вещи: здесь анализируются ряды цен или индексов,
    а корзина должна быть задана отдельным рядом."""
    g_of = (lambda r: str(r[group])) if group else (lambda r: 'ряд')
    groups = {}
    for r in records: groups.setdefault(g_of(r), []).append(r)
    m = int(season_length); res = {}; tbl = []; summ = []; warns = []
    series_chart = []; xlabels = None
    for g, rs in groups.items():
        rs = sorted_rows(rs, period); per = [str(r[period]) for r in rs]; require_complete(per, f'цены ({g})')
        p = np.array([num(r[price], price) for r in rs])
        if (p <= 0).any(): raise ValueError(f'Цены ({g}) должны быть положительными')
        if len(p) < 2: raise ValueError(f'Для ряда «{g}» нужно минимум 2 периода')
        bi = per.index(str(base_period)) if base_period is not None and str(base_period) in per else 0
        idx = p / p[bi] * 100
        mom = [None] + [float((p[i] / p[i - 1] - 1) * 100) for i in range(1, len(p))]
        yoy = [None] * len(p)
        for i in range(m, len(p)): yoy[i] = float((p[i] / p[i - m] - 1) * 100)
        years = (len(p) - 1) / m if m > 0 else None
        cagr = float(((p[-1] / p[0]) ** (1 / years) - 1) * 100) if years and years > 0 else None
        entry = {'last_period': per[-1], 'last_index': float(idx[-1]), 'cumulative_change_pct': float((p[-1] / p[0] - 1) * 100),
                 'last_mom_pct': mom[-1], 'last_yoy_pct': yoy[-1], 'avg_annual_pct': cagr, 'n': len(p), 'base_period': per[bi]}
        if nominal and deflator:
            nom = np.array([num(r[nominal], nominal) for r in rs]); dfl = np.array([num(r[deflator], deflator) for r in rs])
            if (dfl <= 0).any(): raise ValueError('Дефлятор должен быть положительным')
            real = nom / (dfl / 100); entry['real_last'] = float(real[-1]); entry['nominal_last'] = float(nom[-1])
            entry['real_change_pct'] = float((real[-1] / real[0] - 1) * 100); entry['nominal_change_pct'] = float((nom[-1] / nom[0] - 1) * 100)
        res[g] = entry
        tbl.append([g, per[-1], float(idx[-1]), entry['cumulative_change_pct'], yoy[-1], mom[-1], cagr])
        series_chart.append({'name': g, 'values': [float(v) for v in idx]}); xlabels = xlabels if xlabels and len(xlabels) >= len(per) else per
    if len(groups) > 1:
        lc = {g: e['cumulative_change_pct'] for g, e in res.items()}; hi = max(lc, key=lc.get); lo = min(lc, key=lc.get)
        summ.append(f'Сильнее всего цены выросли у «{hi}» ({pct(lc[hi])}), слабее всего у «{lo}» ({pct(lc[lo])}) за весь период.')
        if len({e['n'] for e in res.values()}) > 1: warns.append('Ряды разной длины сравниваются по собственным базовым периодам: проверьте, что периоды совпадают.')
    for g, e in res.items():
        t = f'«{g}»: ' if group else ''
        summ.append(f'{t}индекс на {e["last_period"]} = {fnum(e["last_index"])} (база {e["base_period"]} = 100), за весь период {pct(e["cumulative_change_pct"])}.')
        if e['last_yoy_pct'] is not None: summ.append(f'{t}инфляция к году назад: {pct(e["last_yoy_pct"])}.')
        if 'real_change_pct' in e: summ.append(f'{t}номинально {pct(e["nominal_change_pct"])}, с поправкой на цены (реально) {pct(e["real_change_pct"])}.')
    summ.append('Напоминание: цена товара, индекс цен и стоимость товарной корзины — разные показатели; сравнивайте только однотипные.')
    return {'groups': res, 'summary_ru': summ, 'warnings': warns,
            'tables': {'prices': table(['Ряд', 'Последний период', 'Индекс', 'За весь период, %', 'К году назад, %', 'К пред. периоду, %', 'В среднем за год, %'], tbl, 'Динамика цен')},
            'chart': {'type': 'line', 'title': 'Индекс цен (база = 100)', 'x': xlabels, 'series': series_chart}}

# ---------------------------------------------------------------- M04
def m04_productivity(records, group='industry', period='year', output='value_added', labour='employment', hours=None, capital=None, alpha=0.3):
    """Производительность труда и капитала, ОФП (остаток Солоу, веса α и 1−α) — по группам и годам.
    Динамика осмысленна только для выпуска в постоянных ценах."""
    if not 0 < alpha < 1: raise ValueError('alpha должна быть между 0 и 1')
    by = {}
    for r in records: by.setdefault(str(r[group]), []).append(r)
    res = {}; tbl = []; summ = []; warns = ['Динамика производительности достоверна только если выпуск задан в постоянных ценах.']
    lines = []; xs = None
    for g, rs in by.items():
        rs = sorted_rows(rs, period); per = [str(r[period]) for r in rs]; require_complete(per, f'производительность ({g})')
        Y = np.array([num(r[output], output) for r in rs]); L = np.array([num(r[labour], labour) for r in rs])
        if (Y <= 0).any() or (L <= 0).any(): raise ValueError(f'«{g}»: выпуск и занятость должны быть положительными')
        H = np.array([num(r[hours], hours) for r in rs]) if hours else None
        K = np.array([num(r[capital], capital) for r in rs]) if capital else None
        if K is not None and (K <= 0).any(): raise ValueError(f'«{g}»: капитал должен быть положительным')
        lp = Y / L; e = {'periods': per, 'labour_productivity': lp.tolist()}
        if H is not None: e['output_per_hour'] = (Y / H).tolist()
        if K is not None:
            e['capital_productivity'] = (Y / K).tolist(); e['capital_per_worker'] = (K / L).tolist()
            gy, gk, gl = np.diff(np.log(Y)), np.diff(np.log(K)), np.diff(np.log(L))
            e['tfp_growth_pct'] = ((gy - alpha * gk - (1 - alpha) * gl) * 100).tolist()
            e['tfp_avg_growth_pct'] = float(np.mean(e['tfp_growth_pct']))
        yrs = len(per) - 1
        e['labour_productivity_cagr_pct'] = float(((lp[-1] / lp[0]) ** (1 / yrs) - 1) * 100) if yrs >= 1 else None
        res[g] = e
        tbl.append([g, per[-1], float(lp[-1]), e['labour_productivity_cagr_pct'], float((Y / K)[-1]) if K is not None else None, e.get('tfp_avg_growth_pct')])
        lines.append({'name': g, 'values': (lp / lp[0] * 100).tolist()}); xs = xs if xs and len(xs) >= len(per) else per
    if len(res) > 1:
        last = {g: e['labour_productivity'][-1] for g, e in res.items()}; mean = float(np.mean(list(last.values())))
        top = max(last, key=last.get); low = min(last, key=last.get)
        summ.append(f'Производительность труда в последний год выше всего у «{top}» ({fnum(last[top])}), ниже всего у «{low}» ({fnum(last[low])}); среднее по группам {fnum(mean)}.')
    for g, e in res.items():
        t = f'«{g}»: ' if len(res) > 1 else ''
        if e['labour_productivity_cagr_pct'] is not None: summ.append(f'{t}производительность труда растёт в среднем на {pct(e["labour_productivity_cagr_pct"])} в год.')
        if 'tfp_avg_growth_pct' in e: summ.append(f'{t}общая факторная производительность (ОФП): {pct(e["tfp_avg_growth_pct"])} в год при доле капитала {fnum(alpha, 2)}. Это расчётная оценка, а не измеренная величина.')
    return {'groups': res, 'alpha': alpha, 'summary_ru': summ, 'warnings': warns,
            'tables': {'summary': table(['Группа', 'Последний период', 'Выпуск на работника', 'Рост в год, %', 'Выпуск на капитал', 'ОФП в год, %'], tbl, 'Производительность')},
            'chart': {'type': 'line', 'title': 'Производительность труда (первый период = 100)', 'x': xs, 'series': lines}}

# ---------------------------------------------------------------- M07
def m07_macro(records, period='year', gdp_real='gdp_real', gdp_nominal='gdp_nominal', employment=None, population=None,
              consumption=None, investment=None, government=None, exports=None, imports=None, inflation_cpi=None):
    rows = sorted_rows(records, period); per = [str(r[period]) for r in rows]; require_complete(per, 'макропоказатели')
    if len(rows) < 2: raise ValueError('Нужно не менее 2 периодов')
    col = lambda c: np.array([num(r[c], c) for r in rows]) if c else None
    R, N = col(gdp_real) if gdp_real else None, col(gdp_nominal) if gdp_nominal else None
    if R is None and N is None: raise ValueError('Нужен реальный или номинальный ВВП')
    n = len(rows); summ = []; warns = []; out = {'periods': per}; tb = []
    g = lambda a: [None] + [float((a[i] / a[i - 1] - 1) * 100) for i in range(1, n)]
    if R is not None:
        out['real_growth_pct'] = g(R); summ.append(f'Реальный ВВП в {per[-1]} вырос на {pct(out["real_growth_pct"][-1])} (за период с {per[0]}: {pct((R[-1] / R[0] - 1) * 100)}).')
    if N is not None: out['nominal_growth_pct'] = g(N)
    if R is not None and N is not None:
        dfl = N / R * 100; out['gdp_deflator'] = dfl.tolist(); out['deflator_inflation_pct'] = g(dfl)
        summ.append(f'Дефлятор ВВП (общий рост цен) в {per[-1]}: {pct(out["deflator_inflation_pct"][-1])}. Номинальный рост {pct(out["nominal_growth_pct"][-1])} складывается из реального роста и роста цен.')
    base = N if N is not None else R
    shares = {}
    for name, c in (('consumption', consumption), ('investment', investment), ('government', government), ('exports', exports), ('imports', imports)):
        if c: a = col(c); shares[name] = (a / base * 100).tolist()
    if shares:
        out['shares_of_gdp_pct'] = shares
        parts = [f'{ {"consumption":"потребление","investment":"инвестиции","government":"госрасходы","exports":"экспорт","imports":"импорт"}[k] } {pct(v[-1])}' for k, v in shares.items()]
        summ.append('Доли в ВВП в последнем периоде: ' + ', '.join(parts) + '.')
    if all(c for c in (consumption, investment, government, exports, imports)) and N is not None:
        total = col(consumption) + col(investment) + col(government) + col(exports) - col(imports)
        resid = (N - total) / N * 100; out['expenditure_identity_residual_pct'] = resid.tolist()
        mx = float(np.max(np.abs(resid)))
        summ.append(f'Проверка ВВП = C + I + G + X − M: расхождение не больше {pct(mx, 2)} от ВВП.' + (' Это больше допустимого округления — проверьте единицы и состав компонент.' if mx > 1 else ''))
        if mx > 1: warns.append('Расходная идентичность ВВП не сходится в пределах 1 %.')
    if employment:
        E = col(employment); X = R if R is not None else N
        out['labour_productivity'] = (X / E).tolist(); summ.append(f'Выпуск на одного занятого: {fnum(out["labour_productivity"][-1], 2)}.' + ('' if R is not None else ' Номинальный, не очищен от инфляции.'))
    if population:
        P = col(population); X = R if R is not None else N; out['gdp_per_capita'] = (X / P).tolist()
    if inflation_cpi:
        out['cpi_inflation'] = col(inflation_cpi).tolist(); summ.append(f'Инфляция по индексу потребительских цен: {pct(out["cpi_inflation"][-1])}.')
    if R is not None and N is None: warns.append('Номинального ВВП нет: дефлятор и доли в ВВП считаются от реального ВВП.')
    for i in range(n):
        tb.append([per[i], float(R[i]) if R is not None else None, float(N[i]) if N is not None else None, out.get('real_growth_pct', [None] * n)[i], out.get('deflator_inflation_pct', [None] * n)[i]])
    out.update({'summary_ru': summ, 'warnings': warns,
                'tables': {'macro': table(['Период', 'Реальный ВВП', 'Номинальный ВВП', 'Реальный рост, %', 'Рост цен (дефлятор), %'], tb, 'Основные показатели')}})
    if 'real_growth_pct' in out: out['chart'] = {'type': 'bar', 'title': 'Реальный рост ВВП, % к предыдущему периоду', 'labels': per[1:], 'values': out['real_growth_pct'][1:]}
    return out

# ---------------------------------------------------------------- M11
def m11_market_comparison(records, market='market', product='product', period='period', price='price', quantity='quantity'):
    """Доли рынков, концентрация (HHI), сравнение цен и их согласованность между рынками."""
    rows = [dict(r) for r in records]
    for r in rows:
        r['_p'] = num(r[price], price) if price and r.get(price) not in (None, '') else None
        r['_q'] = num(r[quantity], quantity) if quantity and r.get(quantity) not in (None, '') else None
    products = sorted({str(r[product]) for r in rows}); out = {}; summ = []; warns = []; tb = []; chart = None
    for pr in products:
        rs = [r for r in rows if str(r[product]) == pr]; last = max(str(r[period]) for r in rs); cur = [r for r in rs if str(r[period]) == last]
        e = {'period': last}
        qs = {str(r[market]): r['_q'] for r in cur if r['_q'] is not None}
        if qs and sum(qs.values()) > 0:
            tot = sum(qs.values()); sh = {k: v / tot * 100 for k, v in qs.items()}; hhi = sum(s ** 2 for s in sh.values())
            top3 = sum(sorted(sh.values(), reverse=True)[:3])
            level = 'низкая' if hhi < 1500 else 'умеренная' if hhi < 2500 else 'высокая'
            e.update({'shares_pct': sh, 'hhi': hhi, 'top3_pct': top3, 'concentration': level})
            lead = max(sh, key=sh.get)
            summ.append(f'«{pr}» ({last}): крупнейший рынок — «{lead}» ({pct(sh[lead])}); концентрация {level} (HHI {fnum(hhi, 0)}; ориентиры: до 1500 низкая, до 2500 умеренная — условные пороги).')
            if chart is None: chart = {'type': 'bar', 'title': f'Доли рынков: {pr}, {last}, %', 'labels': list(sh), 'values': list(sh.values())}
        ps = {str(r[market]): r['_p'] for r in cur if r['_p'] is not None}
        if len(ps) >= 2:
            mean = float(np.mean(list(ps.values()))); e['price_vs_average_pct'] = {k: (v / mean - 1) * 100 for k, v in ps.items()}
            e['price_spread_pct'] = (max(ps.values()) - min(ps.values())) / mean * 100
            hi = max(ps, key=ps.get); lo = min(ps, key=ps.get)
            summ.append(f'«{pr}»: цена выше всего на «{hi}», ниже всего на «{lo}»; разброс {pct(e["price_spread_pct"])} от средней.')
        series = {}
        for r in rs:
            if r['_p'] is not None: series.setdefault(str(r[market]), {})[str(r[period])] = r['_p']
        ms = sorted(series)
        if len(ms) >= 2:
            common = sorted(set.intersection(*[set(series[k]) for k in ms]))
            if len(common) >= 4:
                mat = np.array([[series[k][t] for t in common] for k in ms]); d = np.diff(np.log(mat), axis=1)
                if (d.std(axis=1) > 0).all():
                    c = np.corrcoef(d); e['price_change_correlation'] = {'markets': ms, 'matrix': c.tolist(), 'n': len(common) - 1}
                    off = c[np.triu_indices(len(ms), 1)]; summ.append(f'«{pr}»: цены на рынках меняются {"согласованно" if off.mean() > 0.6 else "не вполне согласованно"} (средняя корреляция изменений {fnum(float(off.mean()), 2)}).')
            else: warns.append(f'«{pr}»: для связи цен нужно минимум 4 общих периода.')
        out[pr] = e
        if 'hhi' in e: tb.append([pr, last, e['hhi'], e['top3_pct'], e['concentration'], e.get('price_spread_pct')])
    if not summ: warns.append('Не найдено достаточно данных: нужны хотя бы количества (для долей) или цены (для сравнения) по двум и более рынкам.')
    return {'products': out, 'summary_ru': summ, 'warnings': warns,
            'tables': {'concentration': table(['Товар', 'Период', 'HHI', 'Доля трёх крупнейших, %', 'Концентрация', 'Разброс цен, %'], tb, 'Концентрация и цены')} if tb else {},
            'chart': chart}
