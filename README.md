# multi-agent-orchestration-tool

A fully autonomous Architect/Reviewer plan-convergence loop. One agent drafts
an implementation plan from human-written requirements; a second agent
critiques it; they go back and forth — with no human in the loop — until the
Reviewer has no blocking objections, or a round cap forces a resolution.

## How it works

- **Architect**: drafts the plan, and on later rounds responds to each of the
  Reviewer's issues (accept / partially accept / reject with a reason), then
  emits a revised plan.
- **Reviewer**: never writes plan text. It only critiques — classifying each
  issue `BLOCKING` or `ADVISORY` — and proposes a concrete fix per issue.
- **Convergence**: the Reviewer returns `status: "AGREED"` (zero blocking
  issues on the current plan).
- **Stall rule**: if the Architect rejects the same issue with the same
  reasoning two rounds running, it's treated as resolved in the Architect's
  favor and the Reviewer is told to stop re-raising it — prevents infinite
  ping-pong on one disputed point.
- **Safety cap**: `--max-iterations` (default 6 round trips). If hit without
  convergence, the run ends with outcome `MAX_ITERATIONS_REACHED` and the
  latest plan plus the last review are both saved — still fully autonomous,
  just honestly reporting it didn't reach agreement.

Full prompt contracts are in [`orchestrator/prompts.py`](orchestrator/prompts.py).

## Backends

Both seats are backend-agnostic. Currently implemented:

- `claude` — Claude Code CLI (`claude -p ... --output-format json --permission-mode bypassPermissions`)
- `cursor` — Cursor CLI (`cursor-agent -p ... --output-format json --trust --force`) —
  **code-complete but untested**; `cursor-agent` wasn't installed on the machine
  this was built on. Install it, then pass `--architect cursor` or `--reviewer cursor`.

Until Cursor is installed, both seats default to `claude` — two Claude Code
instances with different role prompts, which still fully exercises the loop
mechanics. Swapping in Cursor for one seat is the way to get genuine
cross-model diversity (point it at a different underlying model with
`--reviewer-model <name>`, from `cursor-agent --list-models`).

⚠️ `--permission-mode bypassPermissions` and `--trust --force` both skip
normal tool-approval prompts, which is required for unattended headless runs
but means either agent can read/write files in `--workspace` without asking.
Anthropic's own docs recommend bypass mode only inside a sandbox/container —
point `--workspace` at a scratch directory or disposable repo until you trust
this on something real.

## Usage

```bash
pip install -e .

orchestrate run \
  --requirements examples/sample-requirements.md \
  --architect claude --reviewer claude \
  --workspace ./some/scratch/dir \
  --max-iterations 6
```

Each run writes a timestamped folder under `runs/`:

```
runs/20260101T120000Z/
  round_00_architect.json   # initial plan
  round_01_reviewer.json
  round_01_architect.json
  ...
  final_result.json         # outcome, final plan, final review
  transcript.md             # human-readable event log
```

Exit code: `0` on `AGREED`, `2` on `MAX_ITERATIONS_REACHED`, `1` on setup/runtime error.

## Flags

| Flag | Default | Meaning |
|---|---|---|
| `--requirements` | required | Path to the requirements file |
| `--architect` | `claude` | Backend for the Architect seat (`claude`\|`cursor`) |
| `--reviewer` | `claude` | Backend for the Reviewer seat (`claude`\|`cursor`) |
| `--architect-model` | CLI default | Optional model override |
| `--reviewer-model` | CLI default | Optional model override |
| `--workspace` | `.` | Working directory the CLIs run in |
| `--max-iterations` | `6` | Round-trip cap before forced resolution |
| `--runs-dir` | `runs` | Where transcripts are written |

## Status

v0.1 — loop mechanics and Claude backend are implemented and ready to test.
Cursor backend is implemented but unverified pending `cursor-agent` install.
No tests yet.
