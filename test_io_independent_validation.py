import unittest
from io_independent_validation import validate_io

class TestIOValidation(unittest.TestCase):
    def test_reproduces_reference_solution(self):
        A = [[0.2, 0.1], [0.1, 0.2]]
        y = [100, 80]
        reference = [139.68253968253967, 117.46031746031746]
        result = validate_io(A, y, reference)
        self.assertTrue(result["equation_pass"])
        self.assertTrue(result["published_output_comparison"]["pass"])

    def test_rejects_nonproductive_system(self):
        with self.assertRaises(ValueError):
            validate_io([[1.0]], [1.0])

    def test_rejects_negative_coefficients(self):
        with self.assertRaises(ValueError):
            validate_io([[-0.1]], [1.0])

if __name__ == "__main__": unittest.main(verbosity=2)
