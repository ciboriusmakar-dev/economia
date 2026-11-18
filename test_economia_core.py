import unittest
from datetime import date

from economia_core import Observation, goods_balance, solve_leontief, validate_observations


class TestEconomiaCore(unittest.TestCase):
    def test_balanced_goods_account(self):
        result = goods_balance(production=100, imports=20, opening_stocks=5,
                               intermediate_use=40, final_use=60, exports=15,
                               losses=2, closing_stocks=8)
        self.assertTrue(result.is_balanced)
        self.assertAlmostEqual(result.residual, 0.0)

    def test_unbalanced_goods_account(self):
        result = goods_balance(production=100, imports=0, opening_stocks=0,
                               intermediate_use=20, final_use=20, exports=0,
                               losses=0, closing_stocks=0)
        self.assertFalse(result.is_balanced)

    def test_leontief_solution(self):
        result = solve_leontief([[0.2, 0.1], [0.1, 0.2]], [100, 80])
        self.assertAlmostEqual(result.output[0], 139.6825396825, places=8)
        self.assertAlmostEqual(result.output[1], 117.4603174603, places=8)
        self.assertLess(result.equation_residual_norm, 1e-8)

    def test_reject_nonproductive_matrix(self):
        with self.assertRaises(ValueError):
            solve_leontief([[1.0]], [10])

    def test_reject_wrong_dimensions(self):
        with self.assertRaises(ValueError):
            solve_leontief([[0.2, 0.1]], [10])

    def test_observation_metadata(self):
        obs = Observation("country:XX", "GDP", date(2025, 1, 1), date(2025, 12, 31),
                          1000, "million_EUR", "source:demo", "estimate",
                          price_basis="current_prices", currency="EUR")
        self.assertEqual(validate_observations([obs]), [])

    def test_duplicate_observation(self):
        obs = Observation("country:XX", "GDP", date(2025, 1, 1), date(2025, 12, 31),
                          1000, "million_EUR", "source:demo", "fact")
        self.assertTrue(any("дубль" in e for e in validate_observations([obs, obs])))


if __name__ == "__main__":
    unittest.main(verbosity=2)
