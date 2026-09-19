from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from .core import Completion, load_completion, verify
from .local_model import OllamaCritic
from .loop import RunResult, load_tasks, run_task


def demo() -> int:
    completion = Completion(
        task_id="demo",
        task="Validate a local completion",
        status="done",
        summary="Added typed validation and deterministic verification.",
        changed_files=["src/core.py"],
    )
    with tempfile.TemporaryDirectory() as directory:
        report = verify(completion, Path(directory), verification_commands=("python3 -c 'print(\"ok\")'",))
    print(json.dumps({"ready": report.ready, "issues": report.issues}, indent=2))
    return 0 if report.ready else 1


def review_file(path: Path, model: str) -> int:
    completion = load_completion(path)
    local_review = OllamaCritic(model).review(asdict(completion))
    report = verify(completion, path.parent, review=local_review)
    print(json.dumps({"ready": report.ready, "issues": report.issues, "review": local_review.__dict__}, indent=2))
    return 0 if report.ready else 1


def gate(model: str) -> int:
    """Judge one benchmark fixture read from stdin, and print a Verdict.

    This is the entry point a measurement harness calls. It is handed a claim
    and returns a decision, with no workspace assumption baked in.
    """
    fixture = json.loads(sys.stdin.read())
    local_review = OllamaCritic(model).review({"task": fixture["task"], "claim": fixture["claim"]})
    print(json.dumps({"accepted": local_review.accepted, "score": local_review.score, "codes": local_review.codes}))
    return 0


TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"
WORK_DIR = Path(tempfile.gettempdir()) / "typesafe-local-ai-work"


def _summarise(result: RunResult) -> dict:
    judgment = result.judgment
    return {
        "ready": result.ready,
        "deterministic_passed": result.deterministic_passed,
        "attempts": len(result.attempts),
        "repairs_used": result.repairs_used,
        "issues": result.attempts[-1].issues if result.attempts else [],
        "semantic_score": judgment.score if judgment else None,
        "semantic_passed": judgment.passed if judgment else None,
        "error": result.error,
    }


def run_one(task_id: str, model: str, repairs: int) -> int:
    tasks = {task.id: task for task in load_tasks(TASKS_DIR)}
    task = tasks.get(task_id)
    if task is None:
        raise SystemExit(f"unknown task: {task_id}. Known: {', '.join(sorted(tasks))}")
    result = run_task(
        task.id, task.prompt, task.starter, task.ground_truth,
        WORK_DIR / f"{task.id}-run", model=model, max_repairs=repairs,
    )
    print(json.dumps(_summarise(result), indent=2))
    return 0 if result.ready else 1


def bench(model: str, repairs: int) -> int:
    """Run every task unsteered and with one bounded repair pass, side by side.

    Two arms over the same tasks, because a repair loop that is not compared
    against no repair has not been shown to do anything.
    """
    tasks = load_tasks(TASKS_DIR)
    if not tasks:
        raise SystemExit(f"no tasks found under {TASKS_DIR}")

    plain_ready = steered_ready = 0
    rows: list[str] = []
    for task in tasks:
        plain = run_task(
            task.id, task.prompt, task.starter, task.ground_truth,
            WORK_DIR / "plain", model=model, max_repairs=0,
        )
        steered = run_task(
            task.id, task.prompt, task.starter, task.ground_truth,
            WORK_DIR / "steered", model=model, max_repairs=repairs,
        )
        plain_ready += int(plain.ready)
        steered_ready += int(steered.ready)

        def cell(result, key):
            value = _summarise(result)[key]
            return "-" if value is None else str(value)

        rows.append(
            f"{task.id:<10} {cell(plain, 'deterministic_passed'):<6} "
            f"{cell(plain, 'semantic_score'):<6} {cell(plain, 'ready'):<6} | "
            f"{cell(steered, 'deterministic_passed'):<6} "
            f"{cell(steered, 'semantic_score'):<6} {cell(steered, 'ready'):<6} "
            f"{steered.repairs_used}"
        )

    total = len(tasks)
    print(f"model: {model}   tasks: {total}")
    print()
    print(f"{'task':<10} {'det':<6} {'score':<6} {'ready':<6} | {'det':<6} {'score':<6} {'ready':<6} repairs")
    print(f"{'-' * 10} {'-' * 6} {'-' * 6} {'-' * 6} | {'-' * 6} {'-' * 6} {'-' * 6} -------")
    for row in rows:
        print(row)
    print()
    print(f"unsteered      : {plain_ready}/{total} ready")
    print(f"one repair pass: {steered_ready}/{total} ready")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Type-safe local AI quality gate")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("demo")
    review_parser = subparsers.add_parser("review")
    review_parser.add_argument("completion", type=Path)
    review_parser.add_argument("--model", default="llama3.2")
    gate_parser = subparsers.add_parser("gate")
    gate_parser.add_argument("--model", default="llama3.2")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("task")
    run_parser.add_argument("--model", default="llama3.2")
    run_parser.add_argument("--repairs", type=int, default=1)
    bench_parser = subparsers.add_parser("bench")
    bench_parser.add_argument("--model", default="llama3.2")
    bench_parser.add_argument("--repairs", type=int, default=1)
    args = parser.parse_args()
    if args.command == "demo":
        return demo()
    if args.command == "gate":
        return gate(args.model)
    if args.command == "run":
        return run_one(args.task, args.model, args.repairs)
    if args.command == "bench":
        return bench(args.model, args.repairs)
    return review_file(args.completion, args.model)


if __name__ == "__main__":
    raise SystemExit(main())

