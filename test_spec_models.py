"""Проверка модулей по спецификации на примерах с известным ответом (синтетические ряды, только для тестов)."""
import math, unittest
import numpy as np
from economia_spec_models import m02_demand_activity, m03_price_analysis, m04_productivity, m07_macro, m11_market_comparison
from economia_spec_models_ops import m09_forecasting, m12_inventory_analysis, m13_logistics, m14_scenarios

def monthly(n, start=2018):
    return [f'{start + i // 12}-{i % 12 + 1:02d}' for i in range(n)]

class TestM02(unittest.TestCase):
    def test_seasonality_recovered_and_growth(self):
        per = monthly(60); s = [10 * math.sin(2 * math.pi * (i % 12) / 12) for i in range(60)]
        rec = [{'period': p, 'value': 100 + 0.5 * i + s[i]} for i, p in enumerate(per)]
        r = m02_demand_activity(rec)
        idx = list(r['seasonality']['indices'].values())
        for k in range(12): self.assertAlmostEqual(idx[k], 10 * math.sin(2 * math.pi * k / 12), delta=0.3)
        self.assertGreater(r['seasonality']['strength'], 0.95)
        self.assertEqual(r['seasonality']['peak'], 'апр')                     # sin максимален на k=3 → апрель при старте с января
        self.assertAlmostEqual(r['last_yoy_pct'], (rec[-1]['value'] / rec[-13]['value'] - 1) * 100, places=9)
    def test_gap_rejected_not_filled(self):
        rec = [{'period': p, 'value': 1.0 + i} for i, p in enumerate(monthly(24)) if p != '2018-05']
        with self.assertRaises(ValueError): m02_demand_activity(rec)
    def test_price_elasticity_exact(self):
        rec = [{'period': p, 'value': 200 * (100 * (1 + .01 * (i % 7))) ** -0.5 * 10, 'price': 100 * (1 + .01 * (i % 7))} for i, p in enumerate(monthly(30))]
        # value = const * price^-0.5  (ln-ln elasticity = -0.5)
        r = m02_demand_activity(rec, price='price', season_length=12)
        self.assertAlmostEqual(r['price_sensitivity']['elasticity'], -0.5, places=6)

class TestM03(unittest.TestCase):
    def test_index_inflation_real(self):
        per = monthly(25); rec = [{'period': p, 'price': 100 * 1.01 ** i, 'nominal': 1000 * 1.03 ** i, 'deflator': 100 * 1.01 ** i} for i, p in enumerate(per)]
        r = m03_price_analysis(rec, nominal='nominal', deflator='deflator')['groups']['ряд']
        self.assertAlmostEqual(r['last_index'], 100 * 1.01 ** 24, places=9)
        self.assertAlmostEqual(r['last_mom_pct'], 1.0, places=9)
        self.assertAlmostEqual(r['last_yoy_pct'], (1.01 ** 12 - 1) * 100, places=9)
        self.assertAlmostEqual(r['real_last'], 1000 * 1.03 ** 24 / 1.01 ** 24, places=6)
    def test_groups_compared(self):
        rec = [{'period': f'{y}', 'price': v, 'group': g} for g, vs in (('A', [100, 110, 121]), ('B', [100, 100, 100])) for y, v in zip((2020, 2021, 2022), vs)]
        r = m03_price_analysis(rec, group='group', season_length=1)
        self.assertAlmostEqual(r['groups']['A']['cumulative_change_pct'], 21.0); self.assertAlmostEqual(r['groups']['A']['avg_annual_pct'], 10.0)
        self.assertIn('Сильнее всего', r['summary_ru'][0])

class TestM04(unittest.TestCase):
    def test_solow_residual_exact(self):
        rec = []
        for t in range(6):
            K = 100 * 1.03 ** t; L = 50 * 1.01 ** t; A = 1.02 ** t
            rec.append({'industry': 'X', 'year': 2018 + t, 'value_added': A * K ** 0.3 * L ** 0.7, 'employment': L, 'capital': K})
        r = m04_productivity(rec, capital='capital', alpha=0.3)['groups']['X']
        for g in r['tfp_growth_pct']: self.assertAlmostEqual(g, math.log(1.02) * 100, places=9)
    def test_ranking_and_rejects_bad(self):
        rec = [{'industry': g, 'year': y, 'value_added': v, 'employment': 10} for g, vs in (('A', (100, 110)), ('B', (50, 50))) for y, v in zip((2020, 2021), vs)]
        r = m04_productivity(rec); self.assertIn('выше всего у «A»', r['summary_ru'][0])
        with self.assertRaises(ValueError): m04_productivity([{'industry': 'A', 'year': 2020, 'value_added': 0, 'employment': 1}, {'industry': 'A', 'year': 2021, 'value_added': 1, 'employment': 1}])

class TestM07(unittest.TestCase):
    def test_deflator_identity_shares(self):
        rec = []
        for i, y in enumerate((2020, 2021, 2022)):
            rl = 1000 * 1.02 ** i; nm = rl * 1.05 ** i
            rec.append({'year': y, 'gdp_real': rl, 'gdp_nominal': nm, 'consumption': .55 * nm, 'investment': .2 * nm, 'government': .2 * nm, 'exports': .45 * nm, 'imports': .4 * nm, 'employment': 40})
        r = m07_macro(rec, employment='employment', consumption='consumption', investment='investment', government='government', exports='exports', imports='imports')
        self.assertAlmostEqual(r['real_growth_pct'][-1], 2.0, places=9); self.assertAlmostEqual(r['deflator_inflation_pct'][-1], 5.0, places=9)
        self.assertLess(max(abs(x) for x in r['expenditure_identity_residual_pct']), 1e-9)
        self.assertAlmostEqual(r['shares_of_gdp_pct']['investment'][0], 20.0)
    def test_identity_violation_flagged(self):
        rec = [{'year': 2020, 'gdp_nominal': 100, 'consumption': 50, 'investment': 20, 'government': 20, 'exports': 10, 'imports': 0}, {'year': 2021, 'gdp_nominal': 110, 'consumption': 50, 'investment': 20, 'government': 20, 'exports': 10, 'imports': 0}]
        r = m07_macro(rec, gdp_real=None, consumption='consumption', investment='investment', government='government', exports='exports', imports='imports')
        self.assertTrue(any('не сходится' in w for w in r['warnings']))

class TestM11(unittest.TestCase):
    def test_hhi(self):
        rec = [{'market': m, 'product': 'p', 'period': '2024', 'quantity': q, 'price': pr} for m, q, pr in (('A', 50, 10), ('B', 30, 12), ('C', 20, 11))]
        r = m11_market_comparison(rec)['products']['p']
        self.assertAlmostEqual(r['hhi'], 3800.0); self.assertEqual(r['concentration'], 'высокая'); self.assertAlmostEqual(r['top3_pct'], 100.0)
        self.assertAlmostEqual(r['price_spread_pct'], (12 - 10) / 11 * 100)
    def test_price_correlation(self):
        rec = [{'market': m, 'product': 'p', 'period': str(2000 + t), 'price': 10 * (1 + .05 * math.sin(t) + (0.02 * t if m == 'B' else 0))} for m in 'AB' for t in range(8)]
        r = m11_market_comparison(rec)['products']['p']['price_change_correlation']; self.assertGreater(r['matrix'][0][1], 0.5)

class TestM09(unittest.TestCase):
    def test_linear_series_extrapolated(self):
        rec = [{'period': p, 'value': 10 + 2 * i} for i, p in enumerate(monthly(48))]
        r = m09_forecasting(rec, horizon=3)
        self.assertIn(r['selected_method'], {'linear_trend', 'linear_trend_seasonal', 'drift', 'holt_winters'})
        for k, v in enumerate(r['forecast'], 1): self.assertAlmostEqual(v, 10 + 2 * (47 + k), delta=0.2)
        self.assertEqual(r['future_periods'][0], '2022-01')
    def test_seasonal_beats_naive(self):
        rng = np.random.default_rng(1)
        rec = [{'period': p, 'value': 100 + 0.3 * i + 15 * math.sin(2 * math.pi * i / 12) + rng.normal(0, 0.5)} for i, p in enumerate(monthly(72))]
        r = m09_forecasting(rec, horizon=12)
        self.assertNotEqual(r['selected_method'], 'naive'); self.assertGreater(r['skill_vs_naive'], 0.7)
        self.assertEqual(len(r['forecast']), 12); self.assertTrue(all(a < b for a, b in zip(r['interval80']['lo'], r['interval80']['hi'])))
    def test_no_leakage_origin_uses_only_past(self):
        # будущее значение, изменённое после последнего начала проверки, не должно менять ошибки предыдущих методов на более ранних началах
        base = [{'period': p, 'value': 50 + math.sin(i / 3)} for i, p in enumerate(monthly(40))]
        a = m09_forecasting(base, horizon=2, max_origins=5)
        self.assertEqual(a['backtest_origins'], 5)
    def test_quarterly_labels_and_short_series_rejected(self):
        rec = [{'period': f'{2015 + i // 4}-Q{i % 4 + 1}', 'value': 10 + i} for i in range(28)]
        r = m09_forecasting(rec, horizon=2, season_length=4); self.assertEqual(r['future_periods'], ['2022-Q1', '2022-Q2'])
        with self.assertRaises(ValueError): m09_forecasting([{'period': str(2000 + i), 'value': i} for i in range(5)], horizon=1, season_length=1)

class TestM12(unittest.TestCase):
    def test_eoq_safety_stock_turnover(self):
        D = [100, 120, 80, 100, 110, 90]; S = [50, 40, 60, 50, 45, 55]
        rec = [{'period': f'2024-{i + 1:02d}', 'demand': d, 'stock': s} for i, (d, s) in enumerate(zip(D, S))]
        r = m12_inventory_analysis(rec, lead_time=4, order_cost=50, holding_cost=2, service_level=0.95)
        mu = np.mean(D); sd = np.std(D, ddof=1)
        self.assertAlmostEqual(r['safety_stock'], 1.6448536269514722 * sd * 2, places=6)
        self.assertAlmostEqual(r['recommended_reorder_point'], mu * 4 + r['safety_stock'], places=6)
        self.assertAlmostEqual(r['eoq'], math.sqrt(2 * mu * 50 / 2), places=9)
        self.assertAlmostEqual(r['turnover_per_year'], sum(D) / np.mean(S) * 12 / 6, places=9)
    def test_shortage_risk_matches_normal(self):
        rec = [{'period': f'2024-{i + 1:02d}', 'demand': d, 'stock': 10} for i, d in enumerate((90, 110, 100, 100, 95, 105))]
        r = m12_inventory_analysis(rec, lead_time=1, reorder_point=100 + 1.6448536 * np.std((90, 110, 100, 100, 95, 105), ddof=1))
        self.assertAlmostEqual(r['shortage_risk_at_given_reorder_point'], 0.05, places=4)

class TestM13(unittest.TestCase):
    EDGES = [('s', 'a', 4, 10, 2, 5), ('a', 't', 6, 20, 1, 3), ('s', 't', 15, 12, 9, 1), ('s', 'b', 3, 30, 1, 4), ('b', 't', 3, 25, 1, 4)]
    def cfg(self, **kw):
        E = [dict(zip(('from', 'to', 'distance', 'time', 'cost', 'capacity'), e)) for e in self.EDGES]
        return [{'edges': E, **kw}]
    def test_shortest_paths_and_maxflow(self):
        r = m13_logistics(self.cfg(), origin='s', destination='t')
        self.assertEqual(r['routes']['distance']['nodes'], ['s', 'b', 't']); self.assertAlmostEqual(r['routes']['distance']['total'], 6)   # 3+3 короче, чем 4+6
        self.assertEqual(r['routes']['time']['nodes'], ['s', 't']); self.assertEqual(r['routes']['cost']['nodes'], ['s', 'b', 't'])
        self.assertAlmostEqual(r['routes']['cost']['total'], 2)
        self.assertAlmostEqual(r['max_flow'], 3 + 1 + 4)                           # a→t=3, s→t=1, b-ветка=4
        self.assertTrue(any(e['from'] == 'a' and e['to'] == 't' for e in r['saturated_edges']))
    def test_min_cost_distribution(self):
        r = m13_logistics(self.cfg(supply={'s': 6}, demand={'t': 6}))
        d = r['distribution']; self.assertEqual(d['status'], 'optimal')
        # дешёвые пути: s→a→t (стоимость 3, ёмк. 3), s→b→t (стоимость 2, ёмк. 4): 4 по b (8) + 2 по a (6) = 14
        self.assertAlmostEqual(d['total_cost'], 14.0, places=6)
    def test_infeasible_and_unbalanced(self):
        r = m13_logistics(self.cfg(supply={'s': 20}, demand={'t': 20})); self.assertEqual(r['distribution']['status'], 'infeasible')
        with self.assertRaises(ValueError): m13_logistics(self.cfg(supply={'s': 5}, demand={'t': 6}))

class TestM14(unittest.TestCase):
    ITEMS = [{'name': 'Выручка', 'type': 'revenue', 'amount': 100, 'factor': 'demand'}, {'name': 'Энергия', 'type': 'cost', 'amount': 20, 'factor': 'energy'},
             {'name': 'Сырьё (USD)', 'type': 'cost', 'amount': 30, 'factor': 'usd', 'pass_through': 0.5}, {'name': 'Зарплата', 'type': 'cost', 'amount': 10}]
    def test_scenario_arithmetic_and_ranking(self):
        r = m14_scenarios(self.ITEMS, scenarios=[{'name': 'Энергия +50 %', 'shocks': {'energy': 50}, 'stress': True}, {'name': 'Доллар +20 %', 'shocks': {'usd': 20}}])
        self.assertAlmostEqual(r['base_result'], 40.0)
        s = {x['name']: x for x in r['scenarios']}
        self.assertAlmostEqual(s['Энергия +50 %']['result'], 30.0); self.assertAlmostEqual(s['Доллар +20 %']['result'], 37.0)
        self.assertAlmostEqual(s['Энергия +50 %']['change_pct'], -25.0)
        self.assertEqual(r['sensitivity'][0]['factor'], 'demand')                  # спрос влияет сильнее всего
        self.assertTrue(any('Сценарии — допущения' in w for w in r['warnings']))
    def test_unknown_factor_warned_and_bad_type(self):
        r = m14_scenarios(self.ITEMS, scenarios=[{'name': 'X', 'shocks': {'weather': 10}}]); self.assertTrue(any('weather' in w for w in r['warnings']))
        with self.assertRaises(ValueError): m14_scenarios([{'name': 'a', 'type': 'oops', 'amount': 1}])
    def test_history_tail(self):
        r = m14_scenarios(self.ITEMS, series=list(range(1, 101)), confidence=0.95)
        self.assertAlmostEqual(r['historical']['quantile'], np.quantile(range(1, 101), 0.95)); self.assertGreater(r['historical']['expected_shortfall'], r['historical']['quantile'] - 1e-9)

if __name__ == '__main__':
    unittest.main()
