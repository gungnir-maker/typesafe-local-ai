import unittest

from chunks import chunk


class ChunkTests(unittest.TestCase):
    def test_remainder(self):
        self.assertEqual(chunk([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])

    def test_exact_multiple(self):
        self.assertEqual(chunk([1, 2, 3, 4], 2), [[1, 2], [3, 4]])

    def test_empty_input(self):
        self.assertEqual(chunk([], 3), [])

    def test_size_larger_than_input(self):
        self.assertEqual(chunk([1, 2], 5), [[1, 2]])

    def test_size_one(self):
        self.assertEqual(chunk([1, 2, 3], 1), [[1], [2], [3]])

    def test_rejects_zero(self):
        with self.assertRaises(ValueError):
            chunk([1, 2, 3], 0)

    def test_rejects_negative(self):
        with self.assertRaises(ValueError):
            chunk([1, 2, 3], -1)


if __name__ == "__main__":
    unittest.main()
