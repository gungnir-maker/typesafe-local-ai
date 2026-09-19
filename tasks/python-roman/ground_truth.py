import unittest

from roman import int_to_roman


class RomanTests(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(int_to_roman(1), "I")

    def test_subtractive_four(self):
        self.assertEqual(int_to_roman(4), "IV")

    def test_subtractive_nine(self):
        self.assertEqual(int_to_roman(9), "IX")

    def test_teens(self):
        self.assertEqual(int_to_roman(14), "XIV")

    def test_forty(self):
        self.assertEqual(int_to_roman(40), "XL")

    def test_ninety(self):
        self.assertEqual(int_to_roman(90), "XC")

    def test_four_hundred(self):
        self.assertEqual(int_to_roman(400), "CD")

    def test_nine_hundred(self):
        self.assertEqual(int_to_roman(900), "CM")

    def test_mixed(self):
        self.assertEqual(int_to_roman(1990), "MCMXC")

    def test_year(self):
        self.assertEqual(int_to_roman(2024), "MMXXIV")

    def test_largest(self):
        self.assertEqual(int_to_roman(3999), "MMMCMXCIX")

    def test_rejects_zero(self):
        with self.assertRaises(ValueError):
            int_to_roman(0)

    def test_rejects_negative(self):
        with self.assertRaises(ValueError):
            int_to_roman(-1)

    def test_rejects_above_range(self):
        with self.assertRaises(ValueError):
            int_to_roman(4000)


if __name__ == "__main__":
    unittest.main()
