"""One bounded repair pass over a real task, scored by the local gate.

The shape, and why it is this shape:

    task -> local model -> files applied -> real tests run -> judge
                  ^                              |
                  +------ one repair -------------+   (only if the tests failed)

Exactly one repair, matching the limit `typesafe-core` enforces on an Arm.
Repeated repair loops are a known failure mode, and a loop that is allowed to
keep going cannot be measured against one that is not.

The steering message is built from the deterministic evidence — which test
failed, and its output — never from the judge's score. The score separates
garbage from work (measured 0.07-0.32 against 0.59-0.64) but barely separates
work from better work, so it is the wrong thing to climb.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .core import Check, Completion, verify
from .producer import LocalProducer, ProducerError, Proposal, read_workspace
from .typesafe_judge import Judgment, judge_claim

TEST_COMMAND = "python3 -m unittest test_ground_truth -q"
GROUND_TRUTH_MODULE = "test_ground_truth.py"


@dataclass(frozen=True)
class Task:
    id: str
    prompt: str
    starter: Path
    ground_truth: Path


def load_tasks(root: Path) -> list[Task]:
    """Every directory under `root` holding a prompt.txt is one task."""
    tasks: list[Task] = []
    for directory in sorted(Path(root).iterdir()):
        prompt = directory / "prompt.txt"
        if not prompt.is_file():
            continue
        tasks.append(Task(
            id=directory.name,
            prompt=prompt.read_text(),
            starter=directory / "repo",
            ground_truth=directory / "ground_truth.py",
        ))
    return tasks


@dataclass(frozen=True)
class Attempt:
    index: int
    summary: str
    changed_files: list[str]
    checks: list[Check]
    issues: list[str]
    steered: bool


@dataclass(frozen=True)
class RunResult:
    task_id: str
    attempts: list[Attempt]
    judgment: Judgment | None
    ready: bool
    error: str | None = None

    @property
    def deterministic_passed(self) -> bool:
        return bool(self.attempts) and not self.attempts[-1].issues

    @property
    def repairs_used(self) -> int:
        return max(0, len(self.attempts) - 1)


def apply_proposal(workspace: Path, proposal: Proposal) -> list[str]:
    """Write the proposal's files. Paths were validated when it was parsed."""
    written: list[str] = []
    for relative, contents in sorted(proposal.files.items()):
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents)
        written.append(relative)
    return written


def steering_feedback(report_checks: Sequence[Check]) -> str:
    """The repair prompt: what failed and the tail of what it said.

    Deliberately concrete. A model told only "tests failed" has nothing to act
    on, and a model told only a score has less.
    """
    lines = ["These problems were found by running the code, not by reading it:"]
    for check in report_checks:
        if check.passed:
            continue
        lines.append(f"\n- {check.name} failed. Output:\n{check.detail[-800:]}")
    return "\n".join(lines)


def deterministic_check(
    task_id: str,
    task_text: str,
    proposal: Proposal,
    workspace: Path,
    ground_truth: Path,
    check_root: Path,
    index: int,
) -> Any:
    """Run the hidden test against a copy of the workspace.

    A copy, because the hidden test must never appear in the workspace the
    model can read: on the repair pass it would be handed the answer.
    """
    check_dir = check_root / f"{task_id}-check-{index}"
    if check_dir.exists():
        shutil.rmtree(check_dir)
    shutil.copytree(workspace, check_dir)

    target = check_dir / GROUND_TRUTH_MODULE
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ground_truth, target)

    completion = Completion(
        task_id=task_id,
        task=task_text,
        status="done",
        summary=proposal.summary,
        changed_files=sorted(proposal.files),
        tests_claimed=[TEST_COMMAND],
    )
    return verify(
        completion,
        check_dir,
        allowed_prefixes=("." ,),
        verification_commands=(TEST_COMMAND,),
    )


def claim_of(task_id: str, task_text: str, proposal: Proposal) -> dict[str, Any]:
    return {
        "taskId": task_id,
        "task": task_text,
        "status": "done",
        "summary": proposal.summary,
        "changedFiles": sorted(proposal.files),
        "testsClaimed": [TEST_COMMAND],
        "blockers": [],
    }


def run_task(
    task_id: str,
    task_text: str,
    starter: Path,
    ground_truth: Path,
    work_root: Path,
    *,
    model: str = "llama3.2",
    max_repairs: int = 1,
    producer: LocalProducer | None = None,
    judge: bool = True,
    judge_options: Mapping[str, Any] | None = None,
) -> RunResult:
    """Run one task, with at most `max_repairs` repair passes. 0 = unsteered."""
    engine = producer or LocalProducer(model)
    work_root = Path(work_root)
    work_root.mkdir(parents=True, exist_ok=True)

    workspace = work_root / f"{task_id}-work"
    if workspace.exists():
        shutil.rmtree(workspace)
    shutil.copytree(starter, workspace)

    attempts: list[Attempt] = []
    feedback: str | None = None
    report: Any = None
    proposal: Proposal | None = None

    for index in range(max_repairs + 1):
        try:
            proposal = engine.propose(task_text, read_workspace(workspace), feedback)
        except ProducerError as error:
            return RunResult(task_id, attempts, None, False, error=f"producer: {error}")

        apply_proposal(workspace, proposal)
        report = deterministic_check(
            task_id, task_text, proposal, workspace, ground_truth, work_root, index
        )
        attempts.append(Attempt(
            index=index,
            summary=proposal.summary,
            changed_files=sorted(proposal.files),
            checks=list(report.checks),
            issues=list(report.issues),
            steered=index > 0,
        ))
        if not report.issues:
            break
        feedback = steering_feedback(report.checks)

    judgment: Judgment | None = None
    if judge and proposal is not None and report is not None:
        tests = [
            {"command": check.name, "passed": check.passed, "output": check.detail[:800]}
            for check in report.checks
            if check.name == TEST_COMMAND
        ]
        judgment = judge_claim(
            task_text, claim_of(task_id, task_text, proposal), tests, **dict(judge_options or {})
        )

    deterministic_passed = bool(report is not None and not report.issues)
    ready = deterministic_passed and (judgment is None or judgment.passed)
    return RunResult(task_id, attempts, judgment, ready)
