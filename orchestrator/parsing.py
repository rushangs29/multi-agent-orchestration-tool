"""Extract the agent's structured role-contract JSON from raw CLI stdout.

CLI tools invoked with --output-format json wrap the agent's actual text
reply inside an envelope (e.g. Claude Code CLI returns something like
{"type": "result", "result": "<agent's text>", ...}). The agent's own reply
is itself expected to be a raw JSON object per the role prompts in
prompts.py. This module unwraps however many envelope layers are present.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

# Keys various CLI wrappers use to hold the agent's actual text reply.
_TEXT_WRAPPER_KEYS = ("result", "response", "output", "text", "message")

# A payload is recognized as our role contract if it has a status field and
# either a plan (Architect) or issues (Reviewer).
def _is_contract(obj: Any) -> bool:
    return isinstance(obj, dict) and "status" in obj and ("plan" in obj or "issues" in obj)


class AgentResponseError(RuntimeError):
    """Raised when an agent backend's output could not be parsed into the expected contract."""

    def __init__(self, message: str, raw_output: str):
        super().__init__(message)
        self.raw_output = raw_output


def _strip_code_fence(text: str) -> str:
    return _CODE_FENCE_RE.sub("", text.strip()).strip()


def _try_json(text: str) -> Optional[Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def extract_structured_response(raw_stdout: str) -> dict:
    stripped = _strip_code_fence(raw_stdout)
    outer = _try_json(stripped)
    if outer is None:
        raise AgentResponseError("CLI output was not valid JSON at the outer layer.", raw_stdout)

    candidate = outer
    for _ in range(3):  # a couple of wrapper layers is plausible; don't loop forever
        if _is_contract(candidate):
            return candidate
        if not isinstance(candidate, dict):
            break
        next_candidate = None
        for key in _TEXT_WRAPPER_KEYS:
            value = candidate.get(key)
            if isinstance(value, str):
                next_candidate = _try_json(_strip_code_fence(value))
                if next_candidate is not None:
                    break
        if next_candidate is None:
            break
        candidate = next_candidate

    if _is_contract(candidate):
        return candidate

    raise AgentResponseError(
        "Could not locate the role-contract JSON (expected a 'status' field plus "
        "'plan' or 'issues') inside the CLI output.",
        raw_stdout,
    )
