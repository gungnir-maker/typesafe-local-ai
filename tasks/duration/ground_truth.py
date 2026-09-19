import unittest

from durations import parse_duration


class ParseDurationTests(unittest.TestCase):
    def test_hours_and_minutes(self):
        self.assertEqual(parse_duration("1h30m"), 5400)

    def test_seconds_only(self):
        self.assertEqual(parse_duration("45s"), 45)

    def test_hours_only(self):
        self.assertEqual(parse_duration("2h"), 7200)

    def test_minutes_only(self):
        self.assertEqual(parse_duration("10m"), 600)

    def test_all_three(self):
        self.assertEqual(parse_duration("1h2m3s"), 3723)

    def test_zero(self):
        self.assertEqual(parse_duration("0s"), 0)

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            parse_duration("")

    def test_rejects_missing_unit(self):
        with self.assertRaises(ValueError):
            parse_duration("90")

    def test_rejects_unknown_unit(self):
        with self.assertRaises(ValueError):
            parse_duration("1x")

    def test_rejects_repeated_unit(self):
        with self.assertRaises(ValueError):
            parse_duration("1h1h")

    def test_rejects_out_of_order(self):
        with self.assertRaises(ValueError):
            parse_duration("30m1h")

    def test_rejects_non_numeric(self):
        with self.assertRaises(ValueError):
            parse_duration("ah")


if __name__ == "__main__":
    unittest.main()
