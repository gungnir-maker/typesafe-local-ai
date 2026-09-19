from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from .core import Completion, load_completion, verify
from .local_model import OllamaCritic


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Type-safe local AI quality gate")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("demo")
    review_parser = subparsers.add_parser("review")
    review_parser.add_argument("completion", type=Path)
    review_parser.add_argument("--model", default="llama3.2")
    gate_parser = subparsers.add_parser("gate")
    gate_parser.add_argument("--model", default="llama3.2")
    args = parser.parse_args()
    if args.command == "demo":
        return demo()
    if args.command == "gate":
        return gate(args.model)
    return review_file(args.completion, args.model)


if __name__ == "__main__":
    raise SystemExit(main())

