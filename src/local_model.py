from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Mapping

from .core import Review

SERIOUS_SEVERITIES = frozenset({"error", "high", "critical"})

PROMPT_HEADER = (
    "Review this AI completion claim. Return JSON only with keys: accepted (boolean), "
    "score (number 0 to 1), problems (array of {code,message,severity}), "
    "suggestedFixes (array of strings; use an empty array when no fix is needed). "
    "Reject unsupported or incomplete claims, not claims merely because no fix is needed.\n\n"
)


def parse_critic_response(result: Mapping[str, Any], model: str) -> Review:
    """Map raw model JSON onto a Review.

    Acceptance is carried by severity, never by the score: a scalar drifts and
    is easy to launder into confidence.
    """
    problems = [item for item in result.get("problems", []) if isinstance(item, dict)]
    serious = [
        item
        for item in problems
        if str(item.get("severity", "")).lower() in SERIOUS_SEVERITIES
    ]
    accepted = bool(result["accepted"]) and not serious
    codes = ["LOCAL_CRITIC_ACCEPTED" if accepted else "LOCAL_CRITIC_REJECTED"]
    codes.extend(
        f"LOCAL_CRITIC_{str(item.get('severity')).upper()}:{item.get('code') or 'UNSPECIFIED'}"
        for item in serious
    )
    return Review(
        accepted=accepted,
        score=float(result["score"]),
        problems=problems,
        suggested_fixes=result.get("suggestedFixes", []),
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
            return parse_critic_response(json.loads(raw["response"]), self.model)
        except (OSError, urllib.error.URLError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            return Review(
                False,
                0.0,
                [{"code": "LOCAL_MODEL_UNAVAILABLE", "message": str(error), "severity": "high"}],
                source="ollama",
                codes=["LOCAL_MODEL_UNAVAILABLE"],
            )
