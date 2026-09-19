import tempfile
import unittest
from pathlib import Path

from src.core import Check
from src.loop import (
    GROUND_TRUTH_MODULE,
    apply_proposal,
    claim_of,
    deterministic_check,
    load_tasks,
    steering_feedback,
)
from src.producer import Proposal, parse_proposal

TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"


class ProposalParsingTests(unittest.TestCase):
    def test_accepts_a_well_formed_proposal(self):
        proposal = parse_proposal(
            {"summary": "  did the thing  ", "files": {"a.py": "x = 1\n"}}, "test"
        )
        self.assertEqual(proposal.summary, "did the thing")
        self.assertEqual(proposal.files, {"a.py": "x = 1\n"})

    def test_rejects_missing_summary(self):
        with self.assertRaises(ValueError):
            parse_proposal({"files": {"a.py": "x"}}, "test")

    def test_rejects_blank_summary(self):
        with self.assertRaises(ValueError):
            parse_proposal({"summary": "   ", "files": {"a.py": "x"}}, "test")

    def test_rejects_no_files(self):
        with self.assertRaises(ValueError):
            parse_proposal({"summary": "s", "files": {}}, "test")

    def test_rejects_non_string_contents(self):
        with self.assertRaises(ValueError):
            parse_proposal({"summary": "s", "files": {"a.py": 12}}, "test")

    def test_rejects_absolute_path(self):
        with self.assertRaises(ValueError):
            parse_proposal({"summary": "s", "files": {"/etc/passwd": "x"}}, "test")

    def test_rejects_traversal(self):
        with self.assertRaises(ValueError):
            parse_proposal({"summary": "s", "files": {"../outside.py": "x"}}, "test")


class ApplyingProposalTests(unittest.TestCase):
    def test_writes_nested_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            applied = apply_proposal(root, Proposal("s", {"pkg/mod.py": "x = 1\n"}))
            self.assertEqual(applied, ["pkg/mod.py"])
            self.assertEqual((root / "pkg" / "mod.py").read_text(), "x = 1\n")

    def test_overwrites_an_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.py").write_text("old\n")
            apply_proposal(root, Proposal("s", {"a.py": "new\n"}))
            self.assertEqual((root / "a.py").read_text(), "new\n")


class SteeringFeedbackTests(unittest.TestCase):
    def test_names_only_the_failures_and_carries_their_output(self):
        checks = [
            Check("file_policy", True, "ok"),
            Check("python3 -m unittest test_ground_truth -q", False, "AssertionError: 'ab' != 'a-b'"),
        ]
        feedback = steering_feedback(checks)
        self.assertIn("AssertionError", feedback)
        self.assertNotIn("file_policy", feedback)

    def test_output_is_truncated_to_its_tail(self):
        check = Check("cmd", False, "x" * 5000 + "THE-END")
        self.assertTrue(steering_feedback([check]).endswith("THE-END"))

    def test_no_failures_produces_a_header_only(self):
        self.assertNotIn("failed", steering_feedback([Check("cmd", True, "ok")]))


class GroundTruthContainmentTests(unittest.TestCase):
    """The hidden test must never be left where the model can read it."""

    def test_check_copy_does_not_touch_the_model_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "work"
            workspace.mkdir()
            (workspace / "mod.py").write_text("x = 1\n")
            ground_truth = root / "ground_truth.py"
            ground_truth.write_text(
                "import unittest\n\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertTrue(True)\n"
            )

            report = deterministic_check(
                "t", "task", Proposal("s", {"mod.py": "x = 1\n"}),
                workspace, ground_truth, root, 0,
            )

            self.assertTrue(report.ready)
            self.assertFalse((workspace / GROUND_TRUTH_MODULE).exists())
            self.assertTrue((root / "t-check-0" / GROUND_TRUTH_MODULE).exists())

    def test_two_tasks_do_not_share_a_check_directory(self):
        """A check dir keyed only by attempt index is overwritten by the next task."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "ground_truth.py"
            source.write_text(
                "import unittest\n\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertTrue(True)\n"
            )
            for task_id in ("alpha", "beta"):
                workspace = root / f"{task_id}-work"
                workspace.mkdir()
                (workspace / "mod.py").write_text("x = 1\n")
                deterministic_check(
                    task_id, "task", Proposal("s", {"mod.py": "x = 1\n"}),
                    workspace, source, root, 1,
                )

            self.assertTrue((root / "alpha-check-1").is_dir())
            self.assertTrue((root / "beta-check-1").is_dir())


class TaskLoadingTests(unittest.TestCase):
    def test_finds_the_shipped_tasks(self):
        ids = sorted(task.id for task in load_tasks(TASKS_DIR))
        self.assertEqual(ids, ["chunk", "duration", "slugify"])

    def test_every_task_has_a_prompt_a_starter_and_a_ground_truth(self):
        for task in load_tasks(TASKS_DIR):
            with self.subTest(task=task.id):
                self.assertTrue(task.prompt.strip())
                self.assertTrue(task.starter.is_dir())
                self.assertTrue(task.ground_truth.is_file())


class ClaimShapeTests(unittest.TestCase):
    def test_claim_matches_the_adapter_contract_keys(self):
        claim = claim_of("t", "do it", Proposal("did it", {"a.py": "x"}))
        self.assertEqual(
            sorted(claim),
            ["blockers", "changedFiles", "status", "summary", "task", "taskId", "testsClaimed"],
        )
        self.assertEqual(claim["status"], "done")
        self.assertEqual(claim["changedFiles"], ["a.py"])


if __name__ == "__main__":
    unittest.main()
