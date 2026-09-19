import unittest

from csvline import parse_csv_line


class CsvLineTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse_csv_line("a,b,c"), ["a", "b", "c"])

    def test_empty_field(self):
        self.assertEqual(parse_csv_line("a,,c"), ["a", "", "c"])

    def test_quoted_comma(self):
        self.assertEqual(parse_csv_line('"a,b",c'), ["a,b", "c"])

    def test_escaped_quote(self):
        self.assertEqual(parse_csv_line('"say ""hi""",x'), ['say "hi"', "x"])

    def test_simple_quotes(self):
        self.assertEqual(parse_csv_line('a,"b"'), ["a", "b"])

    def test_empty_line(self):
        self.assertEqual(parse_csv_line(""), [""])

    def test_trailing_comma(self):
        self.assertEqual(parse_csv_line("a,"), ["a", ""])

    def test_quote_not_at_field_start_is_literal(self):
        self.assertEqual(parse_csv_line('ab"c,d'), ['ab"c', "d"])

    def test_whitespace_is_preserved(self):
        self.assertEqual(parse_csv_line(" a , b "), [" a ", " b "])

    def test_only_a_quoted_empty_field(self):
        self.assertEqual(parse_csv_line('""'), [""])


if __name__ == "__main__":
    unittest.main()
