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

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .core import Check, Completion, verify
from .producer import LocalProducer, ProducerError, Proposal, read_workspace
from .typesafe_judge import Judgment, judge_claim

TEST_COMMAND = "python3 -m unittest test_ground_truth -q"
GROUND_TRUTH_MODULE = "test_ground_truth.py"

#: Which runner grades a task, keyed by the hidden test's extension. Both
#: commands are repository constants. A model never supplies one.
RUNNERS: dict[str, tuple[str, str]] = {
    ".py": (TEST_COMMAND, GROUND_TRUTH_MODULE),
    ".js": ("node --test test_ground_truth.js", "test_ground_truth.js"),
}


@dataclass(frozen=True)
class Task:
    id: str
    prompt: str
    starter: Path
    ground_truth: Path
    test_command: str
    ground_truth_name: str

    @property
    def suite(self) -> str:
        """Which runner grades this task. For reporting, never for deciding."""
        return "python" if self.test_command.startswith("python3") else "node"


def load_tasks(root: Path) -> list[Task]:
    """Every directory under `root` holding a prompt.txt and a hidden test."""
    tasks: list[Task] = []
    for directory in sorted(Path(root).iterdir()):
        prompt = directory / "prompt.txt"
        if not prompt.is_file():
            continue
        for suffix, (command, name) in RUNNERS.items():
            ground_truth = directory / f"ground_truth{suffix}"
            if ground_truth.is_file():
                tasks.append(Task(
                    id=directory.name,
                    prompt=prompt.read_text(),
                    starter=directory / "repo",
                    ground_truth=ground_truth,
                    test_command=command,
                    ground_truth_name=name,
                ))
                break
        else:
            raise ValueError(f"{directory.name}: needs a ground_truth.py or ground_truth.js")
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


def _contained_target(root: Path, relative: str) -> Path:
    """Where a write would actually land, refusing to leave the workspace.

    Lexical checks reject `..`, but a symlink *inside* the workspace pointing
    outside it passes every lexical test and still writes outside. The parent
    directory is resolved, so the check is made against the real directory the
    bytes would reach, not against the string that names it.
    """
    target = root / relative
    parent = target.parent.resolve()
    if parent != root and root not in parent.parents:
        raise ValueError(f"refusing to write outside the workspace: {relative}")
    if target.is_symlink():
        raise ValueError(f"refusing to write through a symlink: {relative}")
    return target


def apply_proposal(workspace: Path, proposal: Proposal) -> list[str]:
    """Write the proposal's files. Paths were validated when it was parsed."""
    root = workspace.resolve()
    written: list[str] = []
    for relative, contents in sorted(proposal.files.items()):
        target = _contained_target(root, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents)
        written.append(relative)
    return written


_FAILURE_HEADER = re.compile(r"^(?:FAIL|ERROR): (\S+)", re.M)
_CALL_LINE = re.compile(r"^\s+(self\.assert\w+\(.*\))\s*$", re.M)
_ERROR_LINE = re.compile(r"^(\w*Error): (.*)$", re.M)

#: `node --test` writes TAP when it is not attached to a terminal.
_TAP_FAILURE = re.compile(r"^\s*not ok \d+ - (.+?)\s*$", re.M)
_TAP_ERROR = re.compile(r"^\s*error:\s*'?(.+?)'?\s*$", re.M)


def _unittest_summaries(output: str, limit: int) -> list[str]:
    headers = list(_FAILURE_HEADER.finditer(output))
    if not headers:
        return []

    summaries: list[str] = []
    for position, header in enumerate(headers[:limit]):
        end = headers[position + 1].start() if position + 1 < len(headers) else len(output)
        block = output[header.start():end]

        parts = [header.group(1)]
        call = _CALL_LINE.search(block)
        if call:
            parts.append(" ".join(call.group(1).split()))
        said = _ERROR_LINE.search(block)
        if said:
            parts.append(f"{said.group(1)}: {said.group(2).strip()}")
        summaries.append("  ".join(parts)[:300])

    if len(headers) > limit:
        summaries.append(f"...and {len(headers) - limit} more failing tests")
    return summaries


def _tap_summaries(output: str, limit: int) -> list[str]:
    headers = list(_TAP_FAILURE.finditer(output))
    if not headers:
        return []

    summaries: list[str] = []
    for position, header in enumerate(headers[:limit]):
        end = headers[position + 1].start() if position + 1 < len(headers) else len(output)
        block = output[header.start():end]

        parts = [header.group(1)]
        said = _TAP_ERROR.search(block)
        if said:
            parts.append(said.group(1).strip())
        summaries.append("  ".join(parts)[:300])

    if len(headers) > limit:
        summaries.append(f"...and {len(headers) - limit} more failing tests")
    return summaries


def summarise_test_output(output: str, limit: int = 12) -> list[str]:
    """One line per failing test: what it called, and what it produced.

    Test-runner output is mostly framing, and feeding the raw tail to a small
    model buries the signal twice: the informative assertion is not necessarily
    the last one, and the noise between the model and the line that matters is
    ``~~~^^^^`` or a TAP diagnostic block. Measured on `slugify`, an
    800-character tail showed only `test_surrounding_whitespace` while hiding
    `test_basic` — the failure that names the actual bug.

    Two runners are understood: `unittest` (used by the Python tasks) and the
    TAP that `node --test` writes (used by the JavaScript ones).
    """
    return _unittest_summaries(output, limit) or _tap_summaries(output, limit)


def steering_feedback(report_checks: Sequence[Check]) -> str:
    """The repair prompt: which checks failed, and precisely how.

    Concrete on purpose. A model told only "tests failed" has nothing to act
    on, and one handed a raw traceback tail has to find the signal itself —
    which, on the evidence, it does not do.
    """
    failed = [check for check in report_checks if not check.passed]
    if not failed:
        return "No checks failed."

    lines = [
        f"Your previous attempt failed {len(failed)} check(s). Each line below is one "
        "failing test: the call it made, then what it produced.",
    ]
    for check in failed:
        summaries = summarise_test_output(check.detail)
        if summaries:
            lines.append(f"\n{check.name} ran, and these tests failed:")
            lines.extend(f"  {index}. {text}" for index, text in enumerate(summaries, 1))
        else:
            lines.append(f"\n{check.name} did not run cleanly. Its output was:\n{check.detail[-800:]}")

    lines.append(
        "\nFix the cause of each failure in the code. Do not change what the tests "
        "expect, and do not delete the behaviour they check."
    )
    return "\n".join(lines)


def deterministic_check(
    task: Task,
    proposal: Proposal,
    workspace: Path,
    check_root: Path,
    index: int,
) -> Any:
    """Run the hidden test against a copy of the workspace.

    A copy, because the hidden test must never appear in the workspace the
    model can read: on the repair pass it would be handed the answer.
    """
    check_dir = check_root / f"{task.id}-check-{index}"
    if check_dir.exists():
        shutil.rmtree(check_dir)
    shutil.copytree(workspace, check_dir)

    target = check_dir / task.ground_truth_name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(task.ground_truth, target)

    completion = Completion(
        task_id=task.id,
        task=task.prompt,
        status="done",
        summary=proposal.summary,
        changed_files=sorted(proposal.files),
        tests_claimed=[task.test_command],
    )
    return verify(
        completion,
        check_dir,
        allowed_prefixes=("." ,),
        verification_commands=(task.test_command,),
    )


def claim_of(task: Task, proposal: Proposal) -> dict[str, Any]:
    return {
        "taskId": task.id,
        "task": task.prompt,
        "status": "done",
        "summary": proposal.summary,
        "changedFiles": sorted(proposal.files),
        "testsClaimed": [task.test_command],
        "blockers": [],
    }


def run_task(
    task: Task,
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

    workspace = work_root / f"{task.id}-work"
    if workspace.exists():
        shutil.rmtree(workspace)
    shutil.copytree(task.starter, workspace)

    attempts: list[Attempt] = []
    feedback: str | None = None
    report: Any = None
    proposal: Proposal | None = None

    for index in range(max_repairs + 1):
        try:
            proposal = engine.propose(task.prompt, read_workspace(workspace), feedback)
        except ProducerError as error:
            return RunResult(task.id, attempts, None, False, error=f"producer: {error}")

        try:
            apply_proposal(workspace, proposal)
        except ValueError as error:
            # A proposal that tries to escape the workspace ends the run. It is
            # not repairable, and it is not something to write first and judge
            # afterwards.
            return RunResult(task.id, attempts, None, False, error=f"unsafe proposal: {error}")

        report = deterministic_check(task, proposal, workspace, work_root, index)
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
            if check.name == task.test_command
        ]
        judgment = judge_claim(
            task.prompt, claim_of(task, proposal), tests, **dict(judge_options or {})
        )

    deterministic_passed = bool(report is not None and not report.issues)
    ready = deterministic_passed and (judgment is None or judgment.passed)
    return RunResult(task.id, attempts, judgment, ready)
