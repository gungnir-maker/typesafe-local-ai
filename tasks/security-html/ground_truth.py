import unittest

from htmlesc import escape_html


class EscapeHtmlTests(unittest.TestCase):
    def test_angle_brackets(self):
        self.assertEqual(escape_html("<script>"), "&lt;script&gt;")

    def test_ampersand(self):
        self.assertEqual(escape_html("a & b"), "a &amp; b")

    def test_ampersand_is_escaped_first(self):
        self.assertEqual(escape_html("&amp;"), "&amp;amp;")

    def test_double_quote(self):
        self.assertEqual(escape_html('"x"'), "&quot;x&quot;")

    def test_single_quote(self):
        self.assertEqual(escape_html("it's"), "it&#x27;s")

    def test_plain_text_is_unchanged(self):
        self.assertEqual(escape_html("plain text"), "plain text")

    def test_empty(self):
        self.assertEqual(escape_html(""), "")

    def test_script_payload_is_neutralised(self):
        payload = '<img src=x onerror="alert(1)">'
        escaped = escape_html(payload)
        self.assertNotIn("<", escaped)
        self.assertNotIn(">", escaped)
        self.assertNotIn('"', escaped)

    def test_non_string_is_refused(self):
        for value in (None, 3, ["a"], {"a": 1}):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    escape_html(value)


if __name__ == "__main__":
    unittest.main()
