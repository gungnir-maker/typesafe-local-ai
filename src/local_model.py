from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from typing import Any, Mapping

from .core import Review

#: The complete vocabulary a critic may use. Anything else — `INFO`, `warning`,
#: a typo, a missing field — is unknown, and unknown blocks. An unrecognised
#: severity is not a mild one; it is a response the gate cannot interpret, and
#: reading it as harmless is how an unsupported claim gets approved by a word
#: the gate never agreed to honour.
ALLOWED_SEVERITIES = frozenset({"low", "medium", "error", "high", "critical"})

#: Severities that block acceptance on their own. `low` and `medium` are
#: allowed and reported, but do not by themselves reject a claim.
BLOCKING_SEVERITIES = frozenset({"error", "high", "critical"})

PROMPT_HEADER = (
    "Review this AI completion claim. Return JSON only with keys: accepted (boolean), "
    "score (number 0 to 1), problems (array of {code,message,severity}), "
    "suggestedFixes (array of strings; use an empty array when no fix is needed). "
    "severity must be exactly one of: low, medium, high, error, critical. "
    "Reject unsupported or incomplete claims, not claims merely because no fix is needed.\n\n"
)


def parse_critic_response(result: Mapping[str, Any], model: str) -> Review:
    """Map raw model JSON onto a Review, refusing anything it cannot read.

    Three rules, all fail-closed:

    * `accepted` must be an actual boolean. `bool("false")` is `True`, so a
      model answering `"accepted": "false"` would otherwise be read as
      approval.
    * `score` must be a finite number in ``[0, 1]``. It is diagnostic and never
      decides acceptance, but an unreadable one means the response is
      unreadable.
    * A problem's severity must be in the allowed vocabulary. Unknown severity
      blocks, because the gate does not know what it was told.
    """
    if not isinstance(result, Mapping):
        raise ValueError("critic response must be an object")

    accepted_field = result.get("accepted")
    if not isinstance(accepted_field, bool):
        raise ValueError(f"accepted must be a boolean, got {type(accepted_field).__name__}")

    score_field = result.get("score")
    if isinstance(score_field, bool) or not isinstance(score_field, (int, float)):
        raise ValueError(f"score must be a number, got {type(score_field).__name__}")
    score = float(score_field)
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise ValueError(f"score must be finite and within 0..1, got {score!r}")

    problems = result.get("problems")
    if not isinstance(problems, list):
        raise ValueError("problems must be a list")

    fixes = result.get("suggestedFixes", [])
    if not isinstance(fixes, list) or not all(isinstance(item, str) for item in fixes):
        raise ValueError("suggestedFixes must be a list of strings")

    blocking: list[str] = []
    for item in problems:
        if not isinstance(item, Mapping):
            blocking.append("LOCAL_CRITIC_MALFORMED_PROBLEM")
            continue

        severity = item.get("severity")
        if not isinstance(severity, str) or not severity.strip():
            blocking.append("LOCAL_CRITIC_UNKNOWN_SEVERITY:missing")
            continue

        normalized = severity.strip().lower()
        if normalized not in ALLOWED_SEVERITIES:
            blocking.append(f"LOCAL_CRITIC_UNKNOWN_SEVERITY:{severity.strip()}")
        elif normalized in BLOCKING_SEVERITIES:
            blocking.append(f"LOCAL_CRITIC_{normalized.upper()}:{item.get('code') or 'UNSPECIFIED'}")

    accepted = accepted_field and not blocking
    codes = ["LOCAL_CRITIC_ACCEPTED" if accepted else "LOCAL_CRITIC_REJECTED", *blocking]

    return Review(
        accepted=accepted,
        score=score,
        problems=[dict(item) if isinstance(item, Mapping) else {"raw": str(item)} for item in problems],
        suggested_fixes=fixes,
        source=f"ollama:{model}",
        codes=codes,
    )


class OllamaCritic:
    def __init__(self, model: str = "llama3.2", endpoint: str = "http://localhost:11434/api/generate"):
        self.model = model
        self.endpoint = endpoint

    def review(self, payload: Mapping[str, Any]) -> Review:
        """Review any claim payload: a completion record or a benchmark fixture."""
        prompt = PROMPT_HEADER + json.dumps(dict(payload), indent=2)
        body = json.dumps({"model": self.model, "prompt": prompt, "stream": False, "format": "json"}).encode()
        request = urllib.request.Request(self.endpoint, data=body, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = json.loads(response.read())
        except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError) as error:
            return self._failed("LOCAL_MODEL_UNAVAILABLE", str(error))

        try:
            return parse_critic_response(json.loads(raw["response"]), self.model)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            # The model answered, but with something unreadable. That is not the
            # same failure as an unreachable model, and a rerun is not obviously
            # the fix, so it carries its own code.
            return self._failed("LOCAL_MODEL_INVALID_RESPONSE", str(error))

    def _failed(self, code: str, message: str) -> Review:
        return Review(
            accepted=False,
            score=0.0,
            problems=[{"code": code, "message": message, "severity": "high"}],
            source="ollama",
            codes=[code],
        )
