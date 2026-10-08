"""Pluggable CLI backends. Each backend runs one headless turn and returns the
agent's structured role-contract response (see prompts.py).

Both backends inline the role instructions directly into the prompt text
rather than relying on a --system-prompt-style flag, because not every CLI
has one (Cursor's cursor-agent does not, as of writing). This keeps the two
backends behaviorally comparable.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from .parsing import AgentResponseError, extract_structured_response

DEFAULT_TIMEOUT_SECONDS = 600


class BackendError(RuntimeError):
    pass


class AgentBackend:
    name = "base"

    def run(self, prompt: str, workspace: Path) -> dict:
        raise NotImplementedError

    @staticmethod
    def _run_subprocess(cmd: List[str], workspace: Path, timeout: int) -> str:
        try:
            result = subprocess.run(
                cmd,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise BackendError(f"Command not found: {cmd[0]}. Is it installed and on PATH?") from exc
        except subprocess.TimeoutExpired as exc:
            raise BackendError(f"{cmd[0]} timed out after {timeout}s.") from exc

        if result.returncode != 0:
            raise BackendError(
                f"{cmd[0]} exited with status {result.returncode}.\n"
                f"--- stderr ---\n{result.stderr}\n--- stdout ---\n{result.stdout}"
            )
        return result.stdout


class ClaudeCodeBackend(AgentBackend):
    """Headless Claude Code CLI turn.

    Uses --permission-mode bypassPermissions for unattended tool access.
    Anthropic documents this as intended for sandboxed/containerized use, not
    raw production repos -- point --workspace at something you're fine with
    an autonomous agent reading/writing before trusting it with real code.
    """

    name = "claude"

    def __init__(self, model: Optional[str] = None, timeout: int = DEFAULT_TIMEOUT_SECONDS):
        if shutil.which("claude") is None:
            raise BackendError("claude CLI not found on PATH. Install Claude Code CLI first.")
        self.model = model
        self.timeout = timeout

    def run(self, prompt: str, workspace: Path) -> dict:
        cmd = [
            "claude", "-p", prompt,
            "--output-format", "json",
            "--permission-mode", "bypassPermissions",
        ]
        if self.model:
            cmd += ["--model", self.model]
        raw = self._run_subprocess(cmd, workspace, self.timeout)
        try:
            return extract_structured_response(raw)
        except AgentResponseError as exc:
            raise BackendError(f"claude returned unparseable output: {exc}\nRaw:\n{exc.raw_output}") from exc


class CursorBackend(AgentBackend):
    """Headless Cursor CLI (cursor-agent) turn.

    Code-complete but untested on this machine -- cursor-agent was not
    installed when this was written. Swap it into either role via
    --architect cursor / --reviewer cursor once installed.
    """

    name = "cursor"

    def __init__(self, model: Optional[str] = None, timeout: int = DEFAULT_TIMEOUT_SECONDS):
        if shutil.which("cursor-agent") is None:
            raise BackendError(
                "cursor-agent CLI not found on PATH. Install Cursor's CLI first: "
                "https://cursor.com/docs/cli"
            )
        self.model = model
        self.timeout = timeout

    def run(self, prompt: str, workspace: Path) -> dict:
        cmd = [
            "cursor-agent", "-p", prompt,
            "--output-format", "json",
            "--trust", "--force",
        ]
        if self.model:
            cmd += ["--model", self.model]
        raw = self._run_subprocess(cmd, workspace, self.timeout)
        try:
            return extract_structured_response(raw)
        except AgentResponseError as exc:
            raise BackendError(f"cursor-agent returned unparseable output: {exc}\nRaw:\n{exc.raw_output}") from exc


BACKENDS = {
    "claude": ClaudeCodeBackend,
    "cursor": CursorBackend,
}


def build_backend(name: str, model: Optional[str]) -> AgentBackend:
    try:
        cls = BACKENDS[name]
    except KeyError as exc:
        raise BackendError(f"Unknown backend '{name}'. Choices: {', '.join(BACKENDS)}") from exc
    return cls(model=model)
