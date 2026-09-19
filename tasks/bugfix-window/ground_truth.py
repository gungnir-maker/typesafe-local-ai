import unittest

from window import last_n


class LastNTests(unittest.TestCase):
    def test_basic_window(self):
        self.assertEqual(last_n([1, 2, 3, 4, 5], 2), [4, 5])

    def test_whole_sequence_when_n_is_large(self):
        self.assertEqual(last_n([1, 2, 3], 10), [1, 2, 3])

    def test_zero_returns_empty(self):
        self.assertEqual(last_n([1, 2, 3], 0), [])

    def test_n_equals_length(self):
        self.assertEqual(last_n([1, 2, 3], 3), [1, 2, 3])

    def test_n_of_one(self):
        self.assertEqual(last_n([1, 2, 3], 1), [3])

    def test_empty_input(self):
        self.assertEqual(last_n([], 2), [])

    def test_negative_n_raises(self):
        with self.assertRaises(ValueError):
            last_n([1, 2, 3], -1)

    def test_input_is_not_modified(self):
        items = [3, 1, 2]
        last_n(items, 2)
        self.assertEqual(items, [3, 1, 2])

    def test_works_on_a_tuple(self):
        self.assertEqual(last_n((1, 2, 3, 4), 2), [3, 4])


if __name__ == "__main__":
    unittest.main()
