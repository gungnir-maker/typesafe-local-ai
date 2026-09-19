"""The TypeSafe judge: a hosted semantic score for one completion claim.

This is layer 3 of the local pipeline, and it is deliberately shaped like the
adapter in `typesafe-agent-dsh` so the two agree on what a score means and on
the issue codes a failure produces.

Two rules are copied from that adapter on purpose:

* A score outside ``[0, 1]`` is a malformed response, never a strong pass. A
  service that answers ``9`` must not clear every threshold.
* An unreachable judge has not approved anything. Every failure path returns
  ``passed=False``.
"""

from __future__ import annotations

import json
import os
import pathlib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"

#: Shipped threshold. Measured over honest, test-green completions carrying a
#: plainly-stated summary, the score landed at 0.59-0.64, so this sits inside
#: that band rather than above it. See the calibration note in the README.
DEFAULT_THRESHOLD = 0.6

CHECK_ID = "completion_is_supported"

DEFAULT_INSTRUCTIONS = (
    "Based only on the stated task and verification evidence, "
    "is the completion claim supported well enough to hand off?"
)

#: Where the DeepSeek Harness keeps resolved credentials. Read only as a
#: convenience so the judge is runnable without exporting the key; the
#: environment always wins.
CREDENTIAL_STORE = pathlib.Path.home() / ".dsh" / ".credentials.yaml"


@dataclass(frozen=True)
class Judgment:
    score: float | None
    threshold: float
    passed: bool
    model: str = "none"
    codes: list[str] = field(default_factory=list)


def resolve_api_key(ref: str = "TYPESAFE_API_KEY") -> str | None:
    """Environment first, then the Harness credential store.

    Never raises: an unreadable store is the same outcome as an unset key, and
    the caller reports it as unavailable rather than crashing the run.
    """
    ambient = os.environ.get(ref, "")
    if ambient.strip():
        return ambient.strip()

    try:
        text = CREDENTIAL_STORE.read_text()
    except OSError:
        return None

    prefix = f"{ref}:"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            value = stripped[len(prefix):].strip().strip('"').strip("'")
            return value or None
    return None


def _score_from_response(payload: Mapping[str, Any], threshold: float, model: str) -> Judgment:
    answer = payload.get("answers")
    if not isinstance(answer, Mapping):
        raise ValueError("response carries no answers object")

    entry = answer.get(CHECK_ID)
    if not isinstance(entry, Mapping):
        raise ValueError(f"response carries no answer for {CHECK_ID}")

    score = entry.get("noul")
    # A Noul score is a proportion. Anything outside [0, 1] is malformed, and
    # accepting one lets a judge that scores 9 clear every threshold.
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError(f"score is not a number: {score!r}")
    if not (0.0 <= float(score) <= 1.0):
        raise ValueError(f"score outside [0, 1]: {score!r}")

    passed = float(score) >= threshold
    return Judgment(
        score=float(score),
        threshold=threshold,
        passed=passed,
        model=model,
        codes=["SEMANTIC_CHECK_PASSED" if passed else "SEMANTIC_CHECK_FAILED"],
    )


def judge_claim(
    task: str,
    result: Mapping[str, Any],
    tests: Sequence[Mapping[str, Any]] = (),
    *,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    threshold: float = DEFAULT_THRESHOLD,
    instructions: str = DEFAULT_INSTRUCTIONS,
    timeout: int = 60,
    requester: Callable[..., Any] | None = None,
) -> Judgment:
    """Score one claim against its own evidence. Fails closed on every error."""
    key = api_key if api_key is not None else resolve_api_key()
    if not key:
        return Judgment(None, threshold, False, "none", ["TYPESAFE_UNAVAILABLE"])

    body = json.dumps({
        "model": model,
        "state": json.dumps({"task": task, "result": dict(result), "tests": list(tests)}),
        "questions": {CHECK_ID: {"type": "noul", "instructions": instructions}},
    }).encode()

    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )

    try:
        opener = requester or urllib.request.urlopen
        with opener(request, timeout=timeout) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as error:
        return Judgment(None, threshold, False, "none", [f"TYPESAFE_UNAVAILABLE:HTTP_{error.code}"])
    except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError, TypeError):
        return Judgment(None, threshold, False, "none", ["TYPESAFE_UNAVAILABLE"])

    try:
        return _score_from_response(payload, threshold, str(payload.get("model", model)))
    except ValueError:
        # Arrived but cannot be trusted. Retrying the same call would not help,
        # so it is reported as its own outcome rather than folded into
        # "unavailable".
        return Judgment(None, threshold, False, "none", ["SEMANTIC_RESPONSE_INVALID"])
