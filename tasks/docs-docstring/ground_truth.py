import unittest

from mathx import divide


class DivideDocstringTests(unittest.TestCase):
    """Graded by structure, not prose: the docstring must name the exception."""

    def setUp(self):
        self.doc = divide.__doc__ or ""

    def test_a_docstring_exists(self):
        self.assertTrue(self.doc.strip(), "divide has no docstring")

    def test_the_docstring_says_what_it_does(self):
        self.assertIn("divide", self.doc.lower())

    def test_the_docstring_names_the_exception(self):
        self.assertIn("ValueError", self.doc)

    def test_the_docstring_says_when_it_raises(self):
        lowered = self.doc.lower()
        self.assertTrue(
            "zero" in lowered or " 0" in lowered,
            "the docstring must say the error is raised when b is zero",
        )

    def test_the_behaviour_still_works(self):
        self.assertEqual(divide(6, 3), 2)
        with self.assertRaises(ValueError):
            divide(1, 0)

    def test_the_signature_is_unchanged(self):
        import inspect
        self.assertEqual(list(inspect.signature(divide).parameters), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
