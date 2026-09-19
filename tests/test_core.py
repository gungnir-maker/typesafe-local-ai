import tempfile
import unittest
from pathlib import Path

from src.core import OUTPUT_LIMIT, Completion, Review, verify


class CoreTests(unittest.TestCase):
    def test_rejects_file_outside_policy(self):
        completion = Completion("1", "task", "done", "done", ["../secret.txt"])
        report = verify(completion, Path("."))
        self.assertFalse(report.ready)
        self.assertIn("FILE_OUTSIDE_ALLOWED_PREFIX", report.issues)

    def test_accepts_valid_completion_and_check(self):
        completion = Completion("1", "task", "done", "done", ["src/core.py"])
        with tempfile.TemporaryDirectory() as directory:
            report = verify(completion, Path(directory), verification_commands=("python3 -c 'exit(0)'",))
        self.assertTrue(report.ready)

    def test_local_rejection_blocks_ready(self):
        completion = Completion("1", "task", "done", "done", ["src/core.py"])
        report = verify(completion, Path("."), review=Review(False, 0.3))
        self.assertFalse(report.ready)
        self.assertIn("LOCAL_REVIEW_REJECTED", report.issues)

    def test_evidence_keeps_every_failure_not_only_the_last(self):
        """A 1000-character tail silently dropped all but the final failing test."""
        script = (
            "python3 -c \""
            "print('FAIL: test_early ' + 'x' * 1200); "
            "print('FAIL: test_late')\""
        )
        completion = Completion("1", "task", "done", "done", ["src/core.py"])
        with tempfile.TemporaryDirectory() as directory:
            report = verify(completion, Path(directory), verification_commands=(script,))
        detail = next(check for check in report.checks if check.name == script).detail
        self.assertIn("test_early", detail)
        self.assertIn("test_late", detail)

    def test_evidence_is_still_bounded(self):
        script = "python3 -c \"print('x' * 20000 + 'THE-END')\""
        completion = Completion("1", "task", "done", "done", ["src/core.py"])
        with tempfile.TemporaryDirectory() as directory:
            report = verify(completion, Path(directory), verification_commands=(script,))
        detail = next(check for check in report.checks if check.name == script).detail
        self.assertLessEqual(len(detail), OUTPUT_LIMIT)
        self.assertTrue(detail.endswith("THE-END"))


if __name__ == "__main__":
    unittest.main()

