import unittest

from safejoin import safe_join


class SafeJoinTests(unittest.TestCase):
    def test_plain_file(self):
        self.assertEqual(safe_join("/srv/data", "a.txt"), "/srv/data/a.txt")

    def test_nested_file(self):
        self.assertEqual(safe_join("/srv/data", "sub/a.txt"), "/srv/data/sub/a.txt")

    def test_dotdot_that_stays_inside(self):
        self.assertEqual(safe_join("/srv/data", "a/../b.txt"), "/srv/data/b.txt")

    def test_rejects_traversal(self):
        with self.assertRaises(ValueError):
            safe_join("/srv/data", "../etc/passwd")

    def test_rejects_deep_traversal(self):
        with self.assertRaises(ValueError):
            safe_join("/srv/data", "a/../../etc/passwd")

    def test_rejects_absolute(self):
        with self.assertRaises(ValueError):
            safe_join("/srv/data", "/etc/passwd")

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            safe_join("/srv/data", "")

    def test_rejects_escape_hidden_behind_a_neutral_segment(self):
        with self.assertRaises(ValueError):
            safe_join("/srv/data", "a/b/../../../etc/passwd")

    def test_rejects_the_base_itself(self):
        with self.assertRaises(ValueError):
            safe_join("/srv/data", "..")

    def test_sibling_prefix_is_not_containment(self):
        # /srv/database must not count as inside /srv/data.
        with self.assertRaises(ValueError):
            safe_join("/srv/data", "../database/x")


if __name__ == "__main__":
    unittest.main()
