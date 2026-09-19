import re
import unittest
from pathlib import Path

from limits import MAX_RETRIES

README = Path("README.md")


class ReadmeMatchesCodeTests(unittest.TestCase):
    """Graded by structure, not prose: the README must state the code's value."""

    def setUp(self):
        self.text = README.read_text()

    def test_the_readme_states_the_limit_in_the_required_form(self):
        match = re.search(r"MAX_RETRIES\s*=\s*(\d+)", self.text)
        self.assertIsNotNone(match, "README must state `MAX_RETRIES = <number>`")

    def test_the_stated_limit_matches_the_code(self):
        match = re.search(r"MAX_RETRIES\s*=\s*(\d+)", self.text)
        assert match is not None
        self.assertEqual(int(match.group(1)), MAX_RETRIES)

    def test_the_readme_does_not_contradict_itself(self):
        wrong = [
            number for number in re.findall(r"(\d+)\s+retries", self.text)
            if int(number) != MAX_RETRIES
        ]
        self.assertEqual(wrong, [], f"README still claims {wrong} retries")

    def test_the_code_was_not_changed(self):
        self.assertEqual(MAX_RETRIES, 3)

    def test_the_backoff_statement_survives(self):
        self.assertIn("backoff", self.text.lower())


if __name__ == "__main__":
    unittest.main()
