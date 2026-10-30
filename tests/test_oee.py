import unittest
from oee import _indicators


class OeeTest(unittest.TestCase):
    def test_oee_formula(self):
        availability, performance, quality, oee = _indicators({"planned_minutes": 100, "downtime_minutes": 10,
            "target_tons": 1000, "actual_tons": 810, "conforming_tons": 769.5})
        self.assertEqual(availability, 90.0)
        self.assertEqual(performance, 90.0)
        self.assertEqual(quality, 95.0)
        self.assertEqual(oee, 77.0)


if __name__ == "__main__":
    unittest.main()
