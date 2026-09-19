import unittest

from tagevent import add_tag


class AddTagTests(unittest.TestCase):
    def test_first_call(self):
        self.assertEqual(add_tag("a"), ["a"])

    def test_second_call_does_not_see_the_first(self):
        add_tag("a")
        self.assertEqual(add_tag("b"), ["b"])

    def test_several_calls_stay_independent(self):
        for expected in ("x", "y", "z"):
            self.assertEqual(add_tag(expected), [expected])

    def test_existing_tags_are_kept(self):
        self.assertEqual(add_tag("c", ["x"]), ["x", "c"])

    def test_the_given_list_is_not_modified(self):
        original = ["x"]
        snapshot = list(original)
        add_tag("c", original)
        self.assertEqual(original, snapshot)

    def test_explicit_empty_list(self):
        self.assertEqual(add_tag("a", []), ["a"])

    def test_explicit_empty_list_is_not_shared(self):
        first = add_tag("a", [])
        second = add_tag("b", [])
        self.assertEqual(first, ["a"])
        self.assertEqual(second, ["b"])


if __name__ == "__main__":
    unittest.main()
