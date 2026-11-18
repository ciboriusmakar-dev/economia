import math, unittest
import numpy as np
from economia_spec_models_more import m05_cost_analysis, m06_input_output, m08_causal_analysis, m10_production_optimisation


class M05(unittest.TestCase):
    def test_decomposition_adds_up(self):
        recs = [{'period': 2020, 'output': 100, 'materials': 500, 'energy': 100, 'labour': 300, 'depreciation': 50, 'other': 50},
                {'period': 2021, 'output': 120, 'materials': 660, 'energy': 150, 'labour': 330, 'depreciation': 60, 'other': 60}]
        o = m05_cost_analysis(recs)['groups']['Всего']
        self.assertAlmostEqual(o['unit_cost_first'], 10.0); self.assertAlmostEqual(o['unit_cost_last'], 1260 / 120)
        self.assertAlmostEqual(sum(o['contrib'].values()), o['unit_cost_change'])
        self.assertAlmostEqual(o['volume_effect'] + o['unit_cost_effect'], o['total_cost_change'])
        self.assertAlmostEqual(sum(o['shares_last'].values()), 1.0)

    def test_groups_and_kinds(self):
        recs = [{'period': 1, 'group': g, 'output': 10, 'materials': m, 'labour': 10} for g, m in (('A', 10), ('B', 30))]
        r = m05_cost_analysis(recs, group='group', kinds={'labour': 'estimate'})
        self.assertTrue(any('расчётное приближение' in w for w in r['warnings']))
        self.assertTrue(any('Сравнение' in s for s in r['summary_ru']))

    def test_rejects(self):
        with self.assertRaises(ValueError): m05_cost_analysis([{'period': 1, 'output': 0, 'materials': 1}])
        with self.assertRaises(ValueError): m05_cost_analysis([{'period': 1, 'output': 1, 'materials': -1}])
        with self.assertRaises(ValueError): m05_cost_analysis([{'period': 1, 'output': 1, 'materials': 1}], kinds={'materials': 'x'})


class M06(unittest.TestCase):
    CFG = {'industry_ids': ['Агро', 'Пром'], 'Z': [[20, 60], [40, 20]], 'gross_output': [100, 200], 'domestic_final_demand': [20, 140],
           'intermediate_imports': [10, 30], 'value_added': [30, 90]}

    def test_known_example(self):
        r = m06_input_output([self.CFG], demand_change={'Агро': 10})
        np.testing.assert_allclose(r['A'], [[.2, .3], [.4, .1]])
        np.testing.assert_allclose(r['output_multipliers'], [1.3 / .6, 1.1 / .6])
        np.testing.assert_allclose(r['delta_x'] if 'delta_x' in r else r['demand_change']['delta_x'], [15, 10 * .4 / .6])
        np.testing.assert_allclose(r['calculated_output'], [100, 200])
        self.assertTrue(all(c['ok'] for c in r['balance_checks'])); self.assertEqual(len(r['balance_checks']), 3)
        self.assertAlmostEqual(r['import_share'][1], 0.15)

    def test_inconsistent_table_warns(self):
        bad = dict(self.CFG, domestic_final_demand=[50, 140])
        r = m06_input_output([bad]); self.assertTrue(any('НЕ пройдена' in str(row) for t in r['tables'].values() for row in t['rows']))
        self.assertTrue(any('несогласована' in w for w in r['warnings']))

    def test_rejects(self):
        with self.assertRaises(ValueError): m06_input_output([dict(self.CFG, Z=[[100, 100], [100, 100]])])   # непродуктивна
        with self.assertRaises(ValueError): m06_input_output([dict(self.CFG, industry_ids=['a', 'a'])])
        with self.assertRaises(ValueError): m06_input_output([self.CFG], demand_change={'Нет': 1})


def did_data(effect=2.0, pre_trend_gap=0.0):
    recs = []
    for u in range(8):
        tr = 1 if u < 4 else 0; off = 10 + 0.5 * u
        for t in range(1, 7):
            post = 1 if t >= 4 else 0
            recs.append({'unit': f'u{u}', 'period': t, 'treated': tr, 'post': post, 'outcome': off + 1.0 * t + effect * tr * post + pre_trend_gap * tr * t})
    return recs


class M08(unittest.TestCase):
    def test_recovers_effect(self):
        r = m08_causal_analysis(did_data(2.0), period='period', unit='unit', cluster='unit')
        self.assertAlmostEqual(r['effect'], 2.0, places=6)
        self.assertAlmostEqual(r['pretrend']['slope_difference'], 0.0, places=6)
        self.assertAlmostEqual(r['placebo']['effect'], 0.0, places=6)
        self.assertTrue(any('не доказывает причинность' in w for w in r['warnings']))

    def test_detects_pretrend(self):
        r = m08_causal_analysis(did_data(2.0, pre_trend_gap=0.7), period='period', cluster='unit')
        self.assertAlmostEqual(r['pretrend']['slope_difference'], 0.7, places=6)

    def test_controls_and_rejects(self):
        d = did_data(); [x.update(c=float(i % 3)) for i, x in enumerate(d)]
        r = m08_causal_analysis(d, period='period', cluster='unit', controls=['c']); self.assertTrue(r['with_controls'])
        with self.assertRaises(ValueError): m08_causal_analysis([r_ for r_ in did_data() if not (r_['treated'] and r_['post'])])
        with self.assertRaises(ValueError): m08_causal_analysis([dict(x, treated=2) for x in did_data()])


class M10(unittest.TestCase):
    def test_textbook_lp(self):
        cfg = {'products': [{'name': 'X', 'profit': 3, 'uses': {'r1': 1, 'r3': 3}}, {'name': 'Y', 'profit': 5, 'uses': {'r2': 2, 'r3': 2}}], 'resources': {'r1': 4, 'r2': 12, 'r3': 18}}
        r = m10_production_optimisation([cfg])
        self.assertAlmostEqual(r['objective_value'], 36.0); self.assertAlmostEqual(r['plan']['X'], 2.0); self.assertAlmostEqual(r['plan']['Y'], 6.0)
        self.assertEqual(sorted(r['binding']), ['r2', 'r3'])
        self.assertAlmostEqual(r['shadow_prices']['r2'], 1.5); self.assertAlmostEqual(r['shadow_prices']['r3'], 1.0); self.assertAlmostEqual(r['shadow_prices']['r1'], 0.0)
        self.assertAlmostEqual(r['utilisation_pct']['r1'], 50.0)

    def test_integer(self):
        cfg = {'products': [{'name': 'X', 'profit': 5, 'uses': {'a': 6, 'b': 1}}, {'name': 'Y', 'profit': 4, 'uses': {'a': 4, 'b': 2}}], 'resources': {'a': 24, 'b': 6}}
        lp = m10_production_optimisation([cfg]); ip = m10_production_optimisation([cfg], integer=True)
        self.assertAlmostEqual(lp['objective_value'], 21.0); self.assertAlmostEqual(ip['objective_value'], 20.0)
        self.assertTrue(all(abs(v - round(v)) < 1e-9 for v in ip['plan'].values()))

    def test_min_cost_and_infeasible(self):
        cfg = {'products': [{'name': 'A', 'cost': 2, 'min': 10, 'uses': {'r': 1}}, {'name': 'B', 'cost': 3, 'min': 5, 'uses': {'r': 1}}], 'resources': {'r': 100}}
        self.assertAlmostEqual(m10_production_optimisation([cfg], objective='min_cost')['objective_value'], 35.0)
        cfg['resources']['r'] = 10
        self.assertFalse(m10_production_optimisation([cfg], objective='min_cost')['optimal'])
        with self.assertRaises(ValueError): m10_production_optimisation([{'products': [{'name': 'A', 'cost': 1, 'uses': {'r': 1}}], 'resources': {'r': 1}}], objective='min_cost')

    def test_pareto_monotone(self):
        cfg = {'products': [{'name': 'X', 'profit': 3, 'uses': {'r1': 1, 'r3': 3}}, {'name': 'Y', 'profit': 5, 'uses': {'r2': 2, 'r3': 2}}], 'resources': {'r1': 4, 'r2': 12, 'r3': 18}}
        r = m10_production_optimisation([cfg], secondary={'name': 'Энергия', 'coef': {'X': 1, 'Y': 2}, 'sense': 'min'})
        pts = sorted(r['pareto'], key=lambda p: p[1])
        self.assertGreaterEqual(len(pts), 3)
        self.assertTrue(all(b[0] >= a[0] - 1e-9 for a, b in zip(pts, pts[1:])))     # больше энергии — не меньше прибыли


class Wired(unittest.TestCase):
    def test_run_model(self):
        from economia_modules import run_model
        ds = {'dataset_id': 'T', 'source_id': 's', 'origin': 'synthetic', 'data_mode': 'simulation', 'records': [M06.CFG]}
        r = run_model('M06', ds, {}, mode='simulation'); self.assertIn(r['status'], ('COMPLETED', 'COMPLETED_WITH_WARNINGS')); self.assertIn('summary_ru', r['outputs'])
        r2 = run_model('M06', ds, {'method': 'leontief_basic'}, mode='simulation'); self.assertIn(r2['status'], ('COMPLETED', 'COMPLETED_WITH_WARNINGS'))


if __name__ == '__main__':
    unittest.main()
