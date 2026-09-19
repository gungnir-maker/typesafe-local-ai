import unittest

from closure import make_formatters


class MakeFormattersTests(unittest.TestCase):
    def test_each_formatter_uses_its_own_prefix(self):
        formatters = make_formatters(["a", "b"])
        self.assertEqual([f("x") for f in formatters], ["a: x", "b: x"])

    def test_three_prefixes(self):
        formatters = make_formatters(["info", "warn", "error"])
        self.assertEqual(
            [f("m") for f in formatters],
            ["info: m", "warn: m", "error: m"],
        )

    def test_empty_input(self):
        self.assertEqual(make_formatters([]), [])

    def test_a_single_prefix(self):
        formatters = make_formatters(["only"])
        self.assertEqual(formatters[0]("v"), "only: v")

    def test_formatters_created_in_separate_calls_are_independent(self):
        first = make_formatters(["a"])[0]
        second = make_formatters(["b"])[0]
        self.assertEqual(first("v"), "a: v")
        self.assertEqual(second("v"), "b: v")

    def test_repeated_prefixes_are_all_present(self):
        formatters = make_formatters(["a", "a"])
        self.assertEqual([f("x") for f in formatters], ["a: x", "a: x"])


if __name__ == "__main__":
    unittest.main()
