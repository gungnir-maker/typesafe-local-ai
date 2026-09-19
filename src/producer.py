"""The local producer: run one task through a local model.

The model is asked for complete file contents rather than a diff or a tool
call. That keeps the loop to one round trip per attempt and means the only
thing to validate is a JSON object: no patch application, no partial writes.
"""

from __future__ import annotations

import json
import pathlib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

PROMPT_HEADER = """You are completing a coding task.

Return JSON only, with exactly these keys:
  "summary": one or two sentences describing what you changed.
  "files": an object mapping each relative file path you changed to that
           file's COMPLETE new contents. Not a diff. Not a fragment.

Rules:
- Include every file you changed, with its full contents.
- Do not include files you did not change.
- The summary must describe only what the files actually do. Do not claim
  tests you did not run, or behaviour the code does not have.
"""


@dataclass(frozen=True)
class Proposal:
    summary: str
    files: dict[str, str]
    source: str = "none"
    raw: dict[str, Any] = field(default_factory=dict)


def _unsafe_path(path: str) -> bool:
    candidate = pathlib.PurePosixPath(path)
    return candidate.is_absolute() or ".." in candidate.parts or path.strip() == ""


def build_prompt(task: str, workspace_files: Mapping[str, str], feedback: str | None = None) -> str:
    parts = [PROMPT_HEADER, f"\n# Task\n{task}\n", "\n# Current files\n"]
    for path, contents in sorted(workspace_files.items()):
        parts.append(f"\n## {path}\n```\n{contents}\n```\n")
    if feedback:
        parts.append(f"\n# Your previous attempt failed\n{feedback}\n")
        parts.append("\nFix the problems above and return the complete files again.\n")
    return "".join(parts)


def read_workspace(workspace: pathlib.Path) -> dict[str, str]:
    """Every readable text file in the workspace, excluding tests the model must not touch."""
    files: dict[str, str] = {}
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        try:
            files[str(path.relative_to(workspace))] = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
    return files


def parse_proposal(payload: Mapping[str, Any], source: str) -> Proposal:
    summary = payload.get("summary")
    files = payload.get("files")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("summary must be a non-empty string")
    if not isinstance(files, Mapping) or not files:
        raise ValueError("files must be a non-empty object")

    clean: dict[str, str] = {}
    for path, contents in files.items():
        if not isinstance(path, str) or not isinstance(contents, str):
            raise ValueError("files must map strings to strings")
        if _unsafe_path(path):
            raise ValueError(f"unsafe path in proposal: {path}")
        clean[path] = contents

    return Proposal(summary.strip(), clean, source, dict(payload))


class LocalProducer:
    def __init__(self, model: str = "llama3.2", endpoint: str = "http://localhost:11434/api/generate"):
        self.model = model
        self.endpoint = endpoint

    def propose(
        self,
        task: str,
        workspace_files: Mapping[str, str],
        feedback: str | None = None,
        requester: Callable[..., Any] | None = None,
    ) -> Proposal:
        prompt = build_prompt(task, workspace_files, feedback)
        body = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }).encode()
        request = urllib.request.Request(
            self.endpoint, data=body, headers={"Content-Type": "application/json"}
        )

        try:
            opener = requester or urllib.request.urlopen
            with opener(request, timeout=300) as response:
                raw = json.loads(response.read())
            return parse_proposal(json.loads(raw["response"]), f"ollama:{self.model}")
        except (OSError, urllib.error.URLError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ProducerError(str(error)) from error


class ProducerError(RuntimeError):
    """The producer did not return a usable proposal. Never silently repaired."""
