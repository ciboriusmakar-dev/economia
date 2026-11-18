import csv, json, unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).parent
class TestRealDataEmpirical(unittest.TestCase):
 def test_m01_residual_calculation(self):
  with (ROOT/"data"/"pilot_input"/"M01_germany_cement_balance_2021_2025.csv").open(encoding="utf-8", newline="") as f:
   rows=list(csv.DictReader(f))
  self.assertEqual(len(rows),5)
  for r in rows:
   self.assertAlmostEqual(float(r["supply_mt"])-float(r["identified_uses_mt"]),float(r["unexplained_balance_item_mt"]),places=6)
 def test_m04_data_positive_and_fit_finite(self):
  r=json.loads((ROOT/"real_data_empirical_results_M01_M04_M05_M06.json").read_text(encoding="utf-8"))["M04"]
  self.assertEqual(r["sample_n"],6)
  self.assertTrue(all(np.isfinite(v) for v in r["coefficients"].values()))
  self.assertTrue(np.isfinite(r["r_squared_in_sample"]))
 def test_m05_cost_ratios_in_range(self):
  with (ROOT/"data"/"pilot_input"/"M04_M05_germany_business_sectors_2023.csv").open(encoding="utf-8", newline="") as f:
   rows=list(csv.DictReader(f))
  self.assertEqual(len(rows),6)
  for r in rows:
   self.assertGreater(float(r["staff_cost_per_person_eur"]),0)
   self.assertGreaterEqual(float(r["staff_cost_share_turnover"]),0)
   self.assertLess(float(r["staff_cost_share_turnover"]),1)
 def test_m06_sut_identity(self):
  r=json.loads((ROOT/"real_data_empirical_results_M01_M04_M05_M06.json").read_text(encoding="utf-8"))["M06"]["test"]
  self.assertTrue(r["use_identity_passed_with_0_11bn_rounding_tolerance"])
  self.assertFalse(r["leontief_coefficients_estimated"])
 def test_provenance_hashes(self):
  with (ROOT/"real_data_provenance_M01_M04_M05_M06.csv").open(encoding="utf-8", newline="") as f:
   rows=list(csv.DictReader(f))
  self.assertEqual(len(rows),4)
  for r in rows: self.assertEqual(len(r["sha256"]),64)
if __name__=="__main__": unittest.main(verbosity=2)
