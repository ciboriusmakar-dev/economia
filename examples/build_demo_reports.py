"""Строит ДЕМО-отчёты по модулям на ВЫДУМАННЫХ данных (только чтобы показать оформление и формат входа).
Запуск из корня проекта:  python examples/build_demo_reports.py
Входные наборы сохраняются рядом (examples/spec_demo/*.json) и запускаются обычной командой, например:
  python economia_cli.py run M09 examples/spec_demo/M09_input.json --params "{\"horizon\":6}" --mode simulation --report m09.html
"""
import json, math, sys
import numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from economia_modules import run_model
from economia_report import write_report

OUT = ROOT / 'examples' / 'spec_demo'; OUT.mkdir(parents=True, exist_ok=True)
def months(n, y0=2019): return [f'{y0 + i // 12}-{i % 12 + 1:02d}' for i in range(n)]
def ds(name, records): return {'dataset_id': f'DEMO-{name}', 'source_id': 'demo-synthetic', 'origin': 'synthetic', 'data_mode': 'simulation', 'records': records}

demo = {}
per = months(60)
demo['M02'] = (ds('M02', [{'period': p, 'value': round(200 + 0.8 * i + 25 * math.sin(2 * math.pi * (i + 2) / 12) + 3 * math.sin(i * 1.7), 2), 'price': round(50 * (1 + 0.004 * i) * (1 + 0.03 * math.cos(i)), 2)} for i, p in enumerate(per)]), {'price': 'price'})
demo['M03'] = (ds('M03', [{'period': p, 'group': g, 'price': round(100 * (1 + r) ** i * (1 + 0.01 * math.sin(i / 2)), 3)} for g, r in (('Хлеб', .004), ('Энергия', .009), ('Одежда', .002)) for i, p in enumerate(months(36))]), {'group': 'group'})
demo['M04'] = (ds('M04', [{'industry': g, 'year': 2015 + t, 'value_added': a * (1 + gr) ** t * 100, 'employment': 50 * (1 + gl) ** t, 'capital': k * (1.03) ** t} for g, a, gr, gl, k in (('Машиностроение', 1.0, .035, .005, 300), ('Пищевая', .8, .02, .01, 200), ('Химия', 1.2, .03, -.005, 400)) for t in range(9)]), {'capital': 'capital'})
demo['M07'] = (ds('M07', [{'year': 2015 + i, 'gdp_real': round(1000 * 1.021 ** i * (1 + 0.01 * math.sin(i)), 1), 'gdp_nominal': None} for i in range(10)]), {'gdp_nominal': None})
for i, r in enumerate(demo['M07'][0]['records']): r['gdp_nominal'] = round(r['gdp_real'] * 1.03 ** i, 1); r['employment'] = 40 + i * 0.2
demo['M07'] = (demo['M07'][0], {'employment': 'employment'})
demo['M09'] = (ds('M09', [{'period': p, 'value': round(100 + 0.4 * i + 12 * math.sin(2 * math.pi * i / 12) + 2 * math.sin(i * 2.3), 2)} for i, p in enumerate(months(72))]), {'horizon': 12})
demo['M11'] = (ds('M11', [{'market': m, 'product': 'Зерно', 'period': str(2018 + t), 'quantity': q * (1 + .03 * t), 'price': p0 * (1 + .02 * t + .03 * math.sin(t + k))} for k, (m, q, p0) in enumerate((('Север', 500, 20), ('Юг', 320, 22), ('Восток', 150, 25), ('Запад', 90, 21))) for t in range(8)]), {})
demo['M12'] = (ds('M12', [{'period': p, 'demand': round(100 + 15 * math.sin(i) + 8 * math.cos(i * 2.1)), 'stock': round(220 + 40 * math.sin(i / 2))} for i, p in enumerate(months(24))]), {'lead_time': 2, 'order_cost': 60, 'holding_cost': 1.5, 'service_level': 0.95, 'reorder_point': 260})
E = [('Завод', 'Склад А', 120, 2, 2.0, 80), ('Завод', 'Склад Б', 200, 5, 3.0, 60), ('Склад А', 'Магазин 1', 60, 3, 1.5, 50), ('Склад А', 'Магазин 2', 90, 4, 2.5, 40), ('Склад Б', 'Магазин 2', 40, 2, 1.0, 50), ('Склад Б', 'Магазин 3', 70, 3, 2.0, 40)]
demo['M13'] = (ds('M13', [{'edges': [dict(zip(('from', 'to', 'distance', 'time', 'cost', 'capacity'), e)) for e in E], 'supply': {'Завод': 100}, 'demand': {'Магазин 1': 40, 'Магазин 2': 35, 'Магазин 3': 25}}]), {'origin': 'Завод', 'destination': 'Магазин 2'})
demo['M14'] = (ds('M14', [{'name': 'Выручка', 'type': 'revenue', 'amount': 1000, 'factor': 'demand'}, {'name': 'Энергия', 'type': 'cost', 'amount': 150, 'factor': 'energy'}, {'name': 'Импортное сырьё', 'type': 'cost', 'amount': 300, 'factor': 'usd', 'pass_through': 0.8}, {'name': 'Зарплата', 'type': 'cost', 'amount': 250}]),
               {'scenarios': [{'name': 'Энергия +50 %', 'shocks': {'energy': 50}, 'assumptions': 'тарифы растут, переложить в цену нельзя'}, {'name': 'Доллар +25 %', 'shocks': {'usd': 25}}, {'name': 'Стресс: спрос −20 %, энергия +40 %', 'shocks': {'demand': -20, 'energy': 40}, 'stress': True}], 'factor_labels': {'demand': 'Спрос', 'energy': 'Цена энергии', 'usd': 'Курс доллара'}})

demo['M05'] = (ds('M05', [{'period': y, 'group': g, 'output': q, 'materials': q * m, 'energy': q * e, 'labour': q * l, 'depreciation': d, 'other': o} for g, rows in (
    ('Завод А', [(2022, 1000, 5.0, 1.0, 2.5, 600, 400), (2023, 1100, 5.4, 1.4, 2.6, 640, 420), (2024, 1150, 5.5, 1.7, 2.7, 650, 430)]),
    ('Завод Б', [(2022, 800, 5.2, 0.9, 3.0, 700, 380), (2023, 820, 5.3, 1.2, 3.1, 710, 390), (2024, 850, 5.5, 1.5, 3.1, 720, 400)])) for (y, q, m, e, l, d, o) in rows]),
    {'group': 'group', 'kinds': {'depreciation': 'estimate'}})
_A = np.array([[.10, .08, .02, .03], [.20, .13, .12, .10], [.05, .11, .06, .04], [.07, .15, .08, .12]]); _x = np.array([200., 600., 250., 500.]); _Z = _A * _x[None, :]
_imp = np.array([20., 80., 15., 40.]); _y = _x - _Z.sum(axis=1); _va = _x - _Z.sum(axis=0) - _imp
demo['M06'] = (ds('M06', [{'industry_ids': ['Сельхоз', 'Промышленность', 'Энергетика', 'Услуги'], 'Z': _Z.round(6).tolist(), 'gross_output': _x.tolist(), 'domestic_final_demand': _y.round(6).tolist(),
    'intermediate_imports': _imp.tolist(), 'value_added': _va.round(6).tolist()}]), {'demand_change': {'Промышленность': 50}})
_d = []
for u in range(12):
    tr = 1 if u < 6 else 0; off = 20 + 0.8 * u
    for t in range(1, 9):
        _d.append({'unit': f'Регион {u + 1}', 'period': t, 'treated': tr, 'post': 1 if t >= 5 else 0, 'outcome': round(off + 0.6 * t + 1.8 * tr * (1 if t >= 5 else 0) + 0.35 * math.sin(u * 3 + t * 1.7), 3)})
demo['M08'] = (ds('M08', _d), {'period': 'period', 'cluster': 'unit'})
demo['M10'] = (ds('M10', [{'products': [{'name': 'Кирпич', 'profit': 30, 'uses': {'Сырьё': 4, 'Энергия': 3, 'Труд': 2}, 'max': 80}, {'name': 'Плитка', 'profit': 45, 'uses': {'Сырьё': 3, 'Энергия': 5, 'Труд': 4}, 'max': 70}, {'name': 'Блоки', 'profit': 22, 'uses': {'Сырьё': 5, 'Энергия': 2, 'Труд': 1}, 'min': 10}], 'resources': {'Сырьё': 500, 'Энергия': 420, 'Труд': 260}}]),
    {'integer': True, 'secondary': {'name': 'Расход энергии', 'coef': {'Кирпич': 3, 'Плитка': 5, 'Блоки': 2}, 'sense': 'min'}})
for mid, (dset, params) in demo.items():
    (OUT / f'{mid}_input.json').write_text(json.dumps(dset, ensure_ascii=False, indent=1), encoding='utf-8')
    res = run_model(mid, dset, params, mode='simulation')
    write_report(res, OUT / f'{mid}_report.html'); write_report(res, OUT / f'{mid}_report.md')
    print(mid, res['status'], res['errors'] or '')
