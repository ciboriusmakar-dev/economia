"""M01: отчёт «товар × страна» — где производят больше, чем потребляют, и где меньше.

Вход: канонический CSV country,year,product_code,indicator,value,unit,flag
(индикаторы PRODQNT, IMPQNT, EXPQNT; необязательный CONSQNT — потребление, заявленное источником).

Тождество: производство − кажущееся потребление = экспорт − импорт.
  чистый экспортёр  → производство больше потребления (избыток)
  чистый импортёр   → производство меньше потребления (дефицит)
Неполные/скрытые наблюдения не заполняются нулями: они выводятся отдельно.
Если источник сообщает CONSQNT, показывается невязка = кажущееся потребление − CONSQNT
(насколько баланс «сходится»); причины невязки (запасы, потери) отчёт не определяет.
"""
from __future__ import annotations
import csv, json, math
from pathlib import Path
from m01_prodcom_balance import calculate

MISSING = {'', ':', '..', '-'}

def _reported_consumption(path):
    out = {}
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['indicator'].upper() != 'CONSQNT': continue
            v = (r.get('value') or '').strip()
            if v in MISSING or (r.get('flag') or '').strip().upper() in {'C', 'U', ':', '-'}: continue
            x = float(v)
            # отрицательное заявленное потребление допустимо (энергобалансы: расход запасов, чистый экспорт); сверка с ним не делается
            if not math.isfinite(x): raise ValueError(f'Недопустимое CONSQNT {v!r}')
            out[(r['country'], int(r['year']), r['product_code'], r['unit'])] = x
    return out

def build_report(path, tolerance_rel=0.01):
    base = calculate(path)
    reported = _reported_consumption(path)
    rows, incomplete = [], []
    for r in base['rows']:
        if r['status'] != 'APPARENT_CONSUMPTION_ONLY':
            incomplete.append({k: r[k] for k in ('country', 'year', 'product_code', 'unit', 'missing_indicators')}); continue
        p, im, ex, c = r['sold_production'], r['imports'], r['exports'], r['apparent_consumption']
        net = ex - im
        row = {'country': r['country'], 'year': r['year'], 'product_code': r['product_code'], 'unit': r['unit'],
               'production': p, 'imports': im, 'exports': ex, 'apparent_consumption': c,
               'net_exports': net,
               'position': 'избыток (производство > потребление)' if net > 0 else
                           'дефицит (производство < потребление)' if net < 0 else 'баланс',
               'self_sufficiency': (p / c) if c > 0 else None,
               'import_dependence': (im / c) if c > 0 else None,
               'export_share_of_production': (ex / p) if p > 0 else None,
               'identity_check': abs((p - c) - (ex - im)) < 1e-9}
        key = (r['country'], r['year'], r['product_code'], r['unit'])
        if key in reported:
            rep = reported[key]; res = c - rep
            row.update({'reported_consumption': rep, 'residual': res,
                        'residual_rel': (res / rep) if rep > 0 else None,
                        'converges': (abs(res) <= tolerance_rel * rep) if rep > 0 else None})
        rows.append(row)
    # рейтинги по последнему году каждой пары (страна, товар)
    latest = {}
    for r in rows:
        k = (r['country'], r['product_code'], r['unit'])
        if k not in latest or r['year'] > latest[k]['year']: latest[k] = r
    ranking = sorted(latest.values(), key=lambda r: (r['product_code'], -(r['self_sufficiency'] or 0)))
    checked = [r for r in rows if 'converges' in r and r['converges'] is not None]
    return {'model': 'M01', 'report': 'surplus_deficit', 'tolerance_rel': tolerance_rel,
            'n_rows': len(rows), 'n_incomplete': len(incomplete),
            'convergence': {'checked': len(checked), 'converging': sum(r['converges'] for r in checked),
                            'max_abs_residual_rel': max((abs(r['residual_rel']) for r in checked), default=None)},
            'rows': rows, 'latest_by_country_product': ranking, 'incomplete': incomplete,
            'warning': base['warning']}

def to_markdown(rep):
    L = ['# M01: избыток и дефицит по товарам и странам', '']
    c = rep['convergence']
    if c['checked']:
        L += [f"Сходимость с заявленным потреблением (допуск {rep['tolerance_rel']:.1%}): "
              f"{c['converging']} из {c['checked']}; максимальная относительная невязка {c['max_abs_residual_rel']:.2%}.", '']
    L += ['| Страна | Товар | Год | Производство | Импорт | Экспорт | Кажущееся потребление | Позиция | Самообеспеч. | Невязка |',
          '|---|---|---|---:|---:|---:|---:|---|---:|---:|']
    for r in rep['rows']:
        ss = f"{r['self_sufficiency']:.0%}" if r['self_sufficiency'] is not None else '—'
        rs = f"{r['residual']:+.3f}" if 'residual' in r else '—'
        L.append(f"| {r['country']} | {r['product_code']} | {r['year']} | {r['production']:.3f} | {r['imports']:.3f} | "
                 f"{r['exports']:.3f} | {r['apparent_consumption']:.3f} | {r['position']} | {ss} | {rs} |")
    if rep['incomplete']:
        L += ['', '## Неполные или скрытые данные (не заполнены нулями)']
        L += [f"- {x['country']} {x['product_code']} {x['year']}: нет {', '.join(x['missing_indicators'])}" for x in rep['incomplete']]
    L += ['', f"Примечание: {rep['warning']}"]
    return '\n'.join(L)

def main():
    import argparse
    a = argparse.ArgumentParser(description='M01: отчёт избыток/дефицит по товарам и странам')
    a.add_argument('csv'); a.add_argument('--tolerance', type=float, default=0.01)
    a.add_argument('--json', default='m01_surplus_report.json'); a.add_argument('--md', default='m01_surplus_report.md')
    x = a.parse_args(); rep = build_report(x.csv, x.tolerance)
    Path(x.json).write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding='utf-8')
    Path(x.md).write_text(to_markdown(rep), encoding='utf-8'); print(to_markdown(rep))
if __name__ == '__main__': main()
