import unittest

from pagination import page_params


class PageParamsTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(page_params({}, 20, 100), (20, 0))

    def test_explicit_page_and_size(self):
        self.assertEqual(page_params({"page": "3", "size": "10"}, 20, 100), (10, 20))

    def test_size_is_clamped(self):
        self.assertEqual(page_params({"size": "500"}, 20, 100), (100, 0))

    def test_page_only(self):
        self.assertEqual(page_params({"page": "2"}, 20, 100), (20, 20))

    def test_size_only(self):
        self.assertEqual(page_params({"size": "5"}, 20, 100), (5, 0))

    def test_first_page_offset_is_zero(self):
        self.assertEqual(page_params({"page": "1"}, 20, 100), (20, 0))

    def test_returns_ints(self):
        limit, offset = page_params({"page": "4", "size": "7"}, 20, 100)
        self.assertIsInstance(limit, int)
        self.assertIsInstance(offset, int)

    def test_rejects_non_numeric(self):
        for value in ("abc", "", "2.5", "1e3", " "):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    page_params({"page": value}, 20, 100)

    def test_rejects_zero_and_negative(self):
        for value in ("0", "-1"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    page_params({"size": value}, 20, 100)
        with self.assertRaises(ValueError):
            page_params({"page": "0"}, 20, 100)

    def test_ignores_unrelated_keys(self):
        self.assertEqual(page_params({"q": "x", "sort": "name"}, 20, 100), (20, 0))


if __name__ == "__main__":
    unittest.main()
