import unittest
from empirical_harness import calculate_metrics, expanding_window_evaluation


class TestEmpiricalHarness(unittest.TestCase):
    def test_expanding_window_uses_only_past(self):
        seen = []
        def predictor(history):
            seen.append(tuple(history))
            return history[-1]
        result = expanding_window_evaluation([1, 2, 3, 4, 5], predictor, min_train=2)
        self.assertEqual(result['n_forecasts'], 3)
        self.assertEqual(seen, [(1.0, 2.0), (1.0, 2.0, 3.0), (1.0, 2.0, 3.0, 4.0)])
        self.assertTrue(result['chronological_order_preserved'])
        self.assertEqual(result['model_metrics']['MAE'], 1.0)

    def test_metrics_handle_zero_actuals(self):
        m = calculate_metrics([0, 2], [0, 1])
        self.assertEqual(m['MAPE_excluded_zero_actuals'], 1)
        self.assertEqual(m['MAE'], 0.5)
        self.assertIsNotNone(m['sMAPE_percent'])

    def test_rejects_short_series(self):
        with self.assertRaises(ValueError):
            expanding_window_evaluation([1, 2], lambda h: h[-1], min_train=2)

    def test_rejects_non_finite(self):
        with self.assertRaises(ValueError):
            expanding_window_evaluation([1, float('nan'), 3], lambda h: h[-1], min_train=2)

    def test_rejects_non_finite_prediction(self):
        with self.assertRaises(ValueError):
            expanding_window_evaluation([1, 2, 3], lambda h: float('inf'), min_train=2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
