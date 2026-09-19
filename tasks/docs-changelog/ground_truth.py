import re
import unittest
from pathlib import Path

CHANGELOG = Path("CHANGELOG.md")


class ChangelogEntryTests(unittest.TestCase):
    """Graded by structure, not prose."""

    def setUp(self):
        self.text = CHANGELOG.read_text()

    def unreleased(self) -> str:
        match = re.search(r"^##\s+Unreleased\s*$(.*?)(?=^##\s|\Z)", self.text, re.M | re.S)
        self.assertIsNotNone(match, "CHANGELOG must have an `## Unreleased` section")
        return match.group(1)

    def changed_bullets(self) -> list:
        section = self.unreleased()
        match = re.search(r"^###\s+Changed\s*$(.*?)(?=^###\s|^##\s|\Z)", section, re.M | re.S)
        self.assertIsNotNone(match, "Unreleased must have a `### Changed` section")
        return [line for line in match.group(1).splitlines() if line.strip().startswith("-")]

    def test_unreleased_section_exists_and_is_first(self):
        headings = re.findall(r"^##\s+(.+?)\s*$", self.text, re.M)
        self.assertTrue(headings, "no level-2 headings found")
        self.assertEqual(headings[0], "Unreleased")

    def test_a_changed_bullet_mentions_the_timeout(self):
        bullets = self.changed_bullets()
        self.assertTrue(bullets, "no bullets under Unreleased > Changed")
        self.assertTrue(
            any("timeout" in bullet.lower() for bullet in bullets),
            "no bullet mentions the timeout",
        )

    def test_the_bullet_gives_both_numbers(self):
        bullets = " ".join(self.changed_bullets())
        self.assertIn("10", bullets)
        self.assertIn("30", bullets)

    def test_the_new_default_is_30(self):
        bullets = " ".join(self.changed_bullets())
        self.assertRegex(bullets, r"30\s*(?:second|s\b)", "the new default must read as 30 seconds")

    def test_existing_entries_survive(self):
        self.assertIn("## 1.2.0", self.text)
        self.assertIn("Retry support for upstream 5xx responses.", self.text)
        self.assertIn("Backoff no longer grows without bound.", self.text)


if __name__ == "__main__":
    unittest.main()
