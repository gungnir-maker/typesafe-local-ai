from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


#: How much command output is kept as evidence. Enough for a small suite to
#: report every failing test, not just the last one.
OUTPUT_LIMIT = 8_000


def _string_list(value: Any, field: str, *, allow_blank: bool = False) -> list[str]:
    """A list of strings, or a refusal. Never a coercion."""
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list of strings")
    for item in value:
        if not isinstance(item, str) or (not allow_blank and not item.strip()):
            raise ValueError(f"{field} must be a list of non-empty strings")
    return list(value)


@dataclass(frozen=True)
class Completion:
    task_id: str
    task: str
    status: str
    summary: str
    changed_files: list[str]
    tests_claimed: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Completion":
        """Validate a claim strictly, by type rather than by truthiness.

        A claim is attacker-controlled input. A claim that parses into the
        wrong shape scores wrong without saying so, so every field is checked
        for what it actually is.
        """
        if not isinstance(data, dict):
            raise ValueError("completion must be a JSON object")

        required = ("taskId", "task", "status", "summary", "changedFiles")
        missing = [key for key in required if key not in data]
        if missing:
            raise ValueError(f"missing fields: {', '.join(missing)}")

        for key in ("taskId", "task", "summary"):
            value = data[key]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{key} must be a non-empty string")

        if data["status"] not in {"done", "blocked", "in_progress"}:
            raise ValueError("status must be done, blocked, or in_progress")

        return cls(
            task_id=data["taskId"],
            task=data["task"],
            status=data["status"],
            summary=data["summary"],
            changed_files=_string_list(data["changedFiles"], "changedFiles"),
            tests_claimed=_string_list(data.get("testsClaimed", []), "testsClaimed"),
            blockers=_string_list(data.get("blockers", []), "blockers", allow_blank=True),
        )


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class Review:
    accepted: bool
    score: float
    problems: list[dict[str, str]] = field(default_factory=list)
    suggested_fixes: list[str] = field(default_factory=list)
    source: str = "none"
    codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VerificationReport:
    ready: bool
    checks: list[Check]
    review: Review | None
    issues: list[str]


def _path_is_allowed(path: str, allowed_prefixes: tuple[str, ...]) -> bool:
    candidate = Path(path)
    return not candidate.is_absolute() and ".." not in candidate.parts and any(
        candidate == Path(prefix) or Path(prefix) in candidate.parents
        for prefix in allowed_prefixes
    )


def run_verification(command: str, workspace: Path, runner: Callable[..., Any] = subprocess.run) -> Check:
    """Run one operator-supplied command and keep its output as evidence.

    TRUST BOUNDARY. This executes through a shell, so the command string is
    code. It may only ever come from operator configuration — the CLI, a
    config file, or a module constant. It must never be derived from model
    output, a completion claim, or any other untrusted input. `verify` refuses
    a command that is not a non-empty string, and the loop builds its command
    from a constant, never from a proposal.
    """
    try:
        result = runner(
            command,
            cwd=workspace,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return Check(command, False, str(error))
    output = (result.stdout + result.stderr).strip()
    # The tail is kept because a build log puts its errors at the end. The bound
    # was 1000 characters, which silently threw away all but the last failing
    # test in a unittest run — the failure that names the bug is usually the
    # first one, not the last. Matches the adapter's 8000-character evidence
    # limit.
    # ponytail: still a tail slice, so a suite reporting more than 8000
    # characters of failures can still lose its earliest ones. Upgrade by
    # keeping head and tail when a suite outgrows this.
    return Check(command, result.returncode == 0, output[-OUTPUT_LIMIT:])


def verify(
    completion: Completion,
    workspace: Path,
    allowed_prefixes: tuple[str, ...] = ("src", "tests"),
    verification_commands: tuple[str, ...] = (),
    review: Review | None = None,
) -> VerificationReport:
    checks: list[Check] = []
    issues: list[str] = []

    invalid_files = [
        path for path in completion.changed_files
        if not _path_is_allowed(path, allowed_prefixes)
    ]
    checks.append(Check("file_policy", not invalid_files, "ok" if not invalid_files else ", ".join(invalid_files)))
    if invalid_files:
        issues.append("FILE_OUTSIDE_ALLOWED_PREFIX")

    for command in verification_commands:
        # The trust boundary, enforced rather than assumed: a command is only
        # ever run when it is a non-empty string. Anything else fails closed.
        if not isinstance(command, str) or not command.strip():
            checks.append(Check(str(command), False, "command must be a non-empty string"))
            issues.append("INVALID_COMMAND")
            continue
        check = run_verification(command, workspace)
        checks.append(check)
        if not check.passed:
            issues.append(f"CHECK_FAILED:{command}")

    if completion.status != "done":
        issues.append("COMPLETION_NOT_DONE")
    if completion.status == "done" and not completion.summary.strip():
        issues.append("EMPTY_SUMMARY")

    if review is not None and not review.accepted:
        issues.append("LOCAL_REVIEW_REJECTED")

    deterministic_passed = all(check.passed for check in checks)
    ready = deterministic_passed and not issues
    return VerificationReport(ready, checks, review, issues)


def load_completion(path: Path) -> Completion:
    return Completion.from_dict(json.loads(path.read_text()))

