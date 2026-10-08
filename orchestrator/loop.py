"""The convergence state machine: Architect proposes, Reviewer critiques,
repeat until the Reviewer has no BLOCKING issues or the iteration cap is hit.

One "round" = one Reviewer turn + one Architect turn. The Architect always
authors the plan; the Reviewer only critiques and proposes fixes -- it never
writes plan text itself. This keeps authorship unambiguous and avoids two
agents both trying to "own" the plan document.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from .backends import AgentBackend
from .logging_utils import RunLogger
from .prompts import architect_initial_prompt, architect_response_prompt, reviewer_prompt


class LoopResult:
    def __init__(self, outcome: str, plan: Dict, rounds_used: int, final_review: Optional[Dict]):
        self.outcome = outcome  # "AGREED" | "MAX_ITERATIONS_REACHED"
        self.plan = plan
        self.rounds_used = rounds_used
        self.final_review = final_review


def run_loop(
    requirements: str,
    architect: AgentBackend,
    reviewer: AgentBackend,
    workspace: Path,
    max_iterations: int,
    logger: RunLogger,
) -> LoopResult:
    logger.event(f"Round 0: Architect ({architect.name}) drafting initial plan")
    architect_turn = architect.run(architect_initial_prompt(requirements), workspace)
    logger.log_turn(0, "architect", architect_turn)
    plan = architect_turn["plan"]

    rejection_streak: Dict[str, int] = {}
    last_review: Optional[Dict] = None

    for round_num in range(1, max_iterations + 1):
        excluded = [issue_id for issue_id, count in rejection_streak.items() if count >= 2]

        logger.event(f"Round {round_num}: Reviewer ({reviewer.name}) reviewing plan v{plan.get('version')}")
        review = reviewer.run(reviewer_prompt(round_num, plan, excluded), workspace)
        logger.log_turn(round_num, "reviewer", review)
        last_review = review

        if review.get("status") == "AGREED":
            logger.event(f"Round {round_num}: Reviewer AGREED -- converged.")
            return LoopResult("AGREED", plan, round_num, review)

        blocking = [i for i in review.get("issues", []) if i.get("severity") == "BLOCKING"]
        logger.event(f"Round {round_num}: Reviewer requested changes ({len(blocking)} blocking issue(s))")

        logger.event(f"Round {round_num}: Architect ({architect.name}) responding to feedback")
        architect_turn = architect.run(architect_response_prompt(round_num, plan, review), workspace)
        logger.log_turn(round_num, "architect", architect_turn)
        plan = architect_turn["plan"]

        for resp in architect_turn.get("responses_to_reviewer", []):
            issue_id = resp.get("issue_id")
            if not issue_id:
                continue
            if resp.get("decision") == "rejected":
                rejection_streak[issue_id] = rejection_streak.get(issue_id, 0) + 1
            else:
                rejection_streak.pop(issue_id, None)

    logger.event(f"Max iterations ({max_iterations}) reached without convergence.")
    return LoopResult("MAX_ITERATIONS_REACHED", plan, max_iterations, last_review)
