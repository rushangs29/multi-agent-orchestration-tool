"""Per-run transcript: one JSON file per agent turn, plus a final summary."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


class RunLogger:
    def __init__(self, base_dir: Path):
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_dir = base_dir / timestamp
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self._events: List[str] = []

    def event(self, message: str) -> None:
        print(message)
        self._events.append(message)

    def log_turn(self, round_num: int, role: str, payload: dict) -> None:
        path = self.run_dir / f"round_{round_num:02d}_{role}.json"
        path.write_text(json.dumps(payload, indent=2))

    def finalize(self, outcome: str, plan: dict, rounds_used: int, final_review: Optional[dict]) -> None:
        result = {
            "outcome": outcome,
            "rounds_used": rounds_used,
            "final_plan": plan,
            "final_review": final_review,
        }
        (self.run_dir / "final_result.json").write_text(json.dumps(result, indent=2))

        transcript = [
            "# Orchestration run",
            "",
            f"Outcome: **{outcome}** after {rounds_used} round(s)",
            "",
            "## Events",
            "",
        ]
        transcript += [f"- {e}" for e in self._events]
        (self.run_dir / "transcript.md").write_text("\n".join(transcript) + "\n")
