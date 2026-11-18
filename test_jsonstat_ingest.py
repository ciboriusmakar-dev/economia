import unittest
from jsonstat_ingest import parse_jsonstat, JSONStatError


class TestJSONStatIngest(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "class": "dataset", "label": "Fixture dataset", "id": ["geo", "time"],
            "size": [2, 2], "dimension": {
                "geo": {"category": {"index": {"DE": 0, "FR": 1}, "label": {"DE": "Germany", "FR": "France"}}},
                "time": {"category": {"index": ["2023", "2024"], "label": {"2023": "2023", "2024": "2024"}}}
            },
            "value": [10, None, 30, 40], "status": [None, None, "p", None]
        }

    def test_flatten_dimensions_and_keep_missing(self):
        rows, report = parse_jsonstat(self.payload)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["geo_code"], "DE")
        self.assertEqual(rows[0]["time_code"], "2023")
        self.assertEqual(rows[1]["geo_code"], "FR")
        self.assertEqual(rows[1]["status"], "p")
        self.assertEqual(report["missing_cells"], 1)
        self.assertEqual(report["flagged_non_missing_cells"], 1)

    def test_sparse_values(self):
        p = dict(self.payload)
        p["value"] = {"0": 10, "3": 40}
        rows, report = parse_jsonstat(p)
        self.assertEqual([r["value"] for r in rows], [10, 40])
        self.assertEqual(report["missing_cells"], 2)

    def test_reject_dimension_size_mismatch(self):
        p = dict(self.payload)
        p["size"] = [2, 3]
        with self.assertRaises(JSONStatError):
            parse_jsonstat(p)

    def test_reject_bad_value(self):
        p = dict(self.payload)
        p["value"] = [10, None, float("nan"), 40]
        with self.assertRaises(JSONStatError):
            parse_jsonstat(p)


if __name__ == "__main__":
    unittest.main(verbosity=2)
