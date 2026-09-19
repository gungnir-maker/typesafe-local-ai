import unittest

from tags import normalise_tags


class NormaliseTagsTests(unittest.TestCase):
    def test_lowercases_and_deduplicates(self):
        self.assertEqual(normalise_tags(["B", "a", "b"]), ["a", "b"])

    def test_sorts(self):
        self.assertEqual(normalise_tags(["c", "a", "b"]), ["a", "b", "c"])

    def test_empty(self):
        self.assertEqual(normalise_tags([]), [])

    def test_does_not_modify_the_caller_list(self):
        original = ["B", "a", "b"]
        snapshot = list(original)
        normalise_tags(original)
        self.assertEqual(original, snapshot)

    def test_does_not_modify_the_caller_list_when_already_sorted(self):
        original = ["a", "b"]
        snapshot = list(original)
        normalise_tags(original)
        self.assertEqual(original, snapshot)

    def test_returns_a_new_list(self):
        original = ["b"]
        result = normalise_tags(original)
        result.append("x")
        self.assertEqual(original, ["b"])

    def test_handles_duplicates_across_cases(self):
        self.assertEqual(normalise_tags(["A", "a", "A"]), ["a"])

    def test_accepts_a_tuple(self):
        self.assertEqual(normalise_tags(("B", "a")), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
