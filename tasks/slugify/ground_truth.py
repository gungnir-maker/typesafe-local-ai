import unittest

from textlib import slugify


class SlugifyTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Hello, World!"), "hello-world")

    def test_lowercases(self):
        self.assertEqual(slugify("ABC"), "abc")

    def test_collapses_runs(self):
        self.assertEqual(slugify("a---b"), "a-b")

    def test_strips_edges(self):
        self.assertEqual(slugify("--x--"), "x")

    def test_surrounding_whitespace(self):
        self.assertEqual(slugify("  A  B  "), "a-b")

    def test_digits_survive(self):
        self.assertEqual(slugify("Version 2.0"), "version-2-0")

    def test_empty(self):
        self.assertEqual(slugify(""), "")

    def test_punctuation_only(self):
        self.assertEqual(slugify("!!!"), "")


if __name__ == "__main__":
    unittest.main()
