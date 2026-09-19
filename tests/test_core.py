import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


def claim(**overrides):
    base = {
        "taskId": "1", "task": "task", "status": "done", "summary": "done",
        "changedFiles": ["src/a.py"], "testsClaimed": ["pytest"], "blockers": [],
    }
    base.update(overrides)
    return base


class CompletionTypingTests(unittest.TestCase):
    """Every field is checked for what it is, never coerced to what it should be."""

    def test_a_valid_claim_parses(self):
        completion = Completion.from_dict(claim())
        self.assertEqual(completion.task_id, "1")
        self.assertEqual(completion.tests_claimed, ["pytest"])

    def test_a_non_object_is_refused(self):
        for value in ([], "x", 3, None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Completion.from_dict(value)

    def test_missing_fields_are_refused(self):
        with self.assertRaises(ValueError) as caught:
            Completion.from_dict({"taskId": "1"})
        self.assertIn("missing fields", str(caught.exception))

    def test_blank_or_non_string_identity_fields_are_refused(self):
        for field in ("taskId", "task", "summary"):
            for value in ("", "   ", 7, None, ["x"]):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        Completion.from_dict(claim(**{field: value}))

    def test_an_unknown_status_is_refused(self):
        with self.assertRaises(ValueError):
            Completion.from_dict(claim(status="finished"))

    def test_string_lists_are_enforced(self):
        for field in ("changedFiles", "testsClaimed"):
            for value in ("src/a.py", 3, {"a": 1}, None, ["ok", 7], [""]):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        Completion.from_dict(claim(**{field: value}))
        for value in ("broken", 3, {"a": 1}, None, ["ok", 7]):
            with self.subTest(field="blockers", value=value):
                with self.assertRaises(ValueError):
                    Completion.from_dict(claim(blockers=value))

    def test_blockers_may_be_blank_strings(self):
        # The adapter types blockers as plain strings; only the container and
        # the element type are enforced.
        self.assertEqual(Completion.from_dict(claim(blockers=[""])).blockers, [""])

    def test_changed_files_may_be_empty(self):
        self.assertEqual(Completion.from_dict(claim(changedFiles=[])).changed_files, [])


class CommandTrustBoundaryTests(unittest.TestCase):
    """Commands execute through a shell, so only operator strings may reach them."""

    def test_a_non_string_command_fails_closed(self):
        for command in (None, 7, ["npm test"], {"cmd": "npm test"}, "   "):
            with self.subTest(command=command):
                completion = Completion("1", "task", "done", "done", ["src/a.py"])
                report = verify(completion, Path("."), verification_commands=(command,))
                self.assertFalse(report.ready)
                self.assertIn("INVALID_COMMAND", report.issues)

    def test_an_invalid_command_never_reaches_the_shell(self):
        completion = Completion("1", "task", "done", "done", ["src/a.py"])
        with mock.patch("src.core.run_verification") as runner:
            report = verify(completion, Path("."), verification_commands=(None, "   ", 7))
        runner.assert_not_called()
        self.assertIn("INVALID_COMMAND", report.issues)
        self.assertEqual(len(report.checks), 4)  # file policy plus three refusals


if __name__ == "__main__":
    unittest.main()

