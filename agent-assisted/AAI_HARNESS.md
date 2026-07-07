# Agentic AI Infrastructure Harness Plan

This document records how the user-designed draw.io workflow maps onto the repository implementation.

For a detailed handoff to future agents, including project goals, module responsibilities, current progress, known risks, and recommended next tasks, read [`AAI_DEVELOPMENT_GUIDE.md`](./AAI_DEVELOPMENT_GUIDE.md).

## Design correction: LoongFlow-style structure, AAI-defined workflow

AAI should not be a prompt-only Codex wrapper. The intended design is closer to the original full-agent architecture:

```text
Planner -> Executor -> Evaluator -> Summarizer -> Checkpoint / Parent Selection
```

But AAI replaces the workflow semantics and implementation details with the user-designed AAI flow:

- AAI owns the hard workflow state machine.
- Planner decisions are structured artifacts.
- Codex / Claude Code / LoongFlow-compatible backends are executor nodes, not global controllers.
- Evaluator, gate, archive, campaign summary, memory, TRAPS, and population checkpoints are AAI-controlled.
- Failed attempts become negative evidence.

## Core principle

AAI separates workflow governance from agent execution:

- **Workflow engine**: enforces allowed states and transitions in `workflow.json`.
- **Planner**: reads population / summaries / TRAPS and writes structured `plan-*.json` decisions.
- **Executor backend**: Codex is the first backend and edits only bounded child workspaces.
- **Evaluator gate**: pack/local/Modal evaluator plus AAI archive gates decide promotion.
- **Summarizer / memory**: campaign summaries and `harness-ledger.md` / `TRAPS.md` feed later rounds.
- **Population database**: admits variants and failures into checkpointed lineage memory.
- **Mode 3 proposal review**: allows harness changes only when repeated evidence shows a tooling gap.

This prevents reward hacking where a kernel-search agent modifies evaluator, baseline, scoring, or archive memory to make itself look better.

## Workflow mapping

| Draw.io stage | Repository implementation |
| --- | --- |
| Stage -1: requirement parsing / feasibility | `aai_harness.schemas.TaskSpec`, `aai_harness.bootstrap.resolve_task`, `aai_harness.start`, `aai_harness.workflow` |
| Mode 0: build / deploy / first baseline | `aai_harness.bootstrap.bootstrap_baseline`, workflow action `bootstrap_baseline` |
| Stage 1: bounded child optimization | `aai_harness.planner`, `aai_harness.workspace`, `aai_harness.codex_adapter`, `aai_harness.diffing`, `aai_harness.child_eval`, evidence schema in `aai_harness.schemas.EvidenceRecord`, gate checks in `aai_harness.gates` |
| Stage 2: Master Campaign | `aai_harness.campaign`, `aai_harness.archive`, `aai_harness.parent_selection`, `aai_harness.summary`, `aai_harness.memory`, `aai_harness.population` |
| Runtime debugging | `aai_harness.runtime_logging` |
| Mode 3: evidence-backed harness proposal | `aai_harness.proposal`, workflow action `review_proposal` |

## Implemented in version `20260707T181000+0900`

- Added `AAI_DEVELOPMENT_GUIDE.md` as the detailed handoff document for future agents and developers.
- The guide describes project identity, design goals, non-goals, repository layout, module responsibilities, current progress, artifact contracts, workflow commands, known risks, coding guidance, and recommended next tasks.
- Linked the guide from `agent-assisted/README.md` and this design plan.

## Implemented in version `20260707T175500+0900`

- Added `workflow.py` for a hard AAI workflow state machine.
- Added `workflow.json` as the authoritative campaign control artifact.
- Added workflow states: `TASK_RESOLVED`, `BASELINE_READY`, `ROUND_PLANNED`, `CHILD_PREPARED`, `AGENT_RAN`, `EVALUATED`, `GATED_ARCHIVED`, `SUMMARIZED`, `MEMORY_UPDATED`, `PARENT_SELECTED`, and `PROPOSAL_REVIEW`.
- Added workflow actions: `bootstrap_baseline`, `plan_round`, `prepare_child`, `run_agent`, `evaluate_child`, `gate_archive`, `summarize_campaign`, `update_memory`, `select_parent`, and `review_proposal`.
- Added `planner.py` for LoongFlow-style structured planner decisions under `plans/plan-<version>.json` and `.md`.
- Added `population.py` for population/checkpoint lineage memory under `archive/<definition>/population/`.
- Added CLI commands: `workflow-init`, `workflow-status`, `workflow-advance`, `plan-round`, `admit-population`, and `population-status`.
- Updated `start` so a new AAI campaign creates `workflow.json` automatically.

## Implemented in version `20260707T174000+0900`

- Removed legacy retained-kernel directories, legacy skills, historical report, and old full-agent trace/writeup package.
- Rewrote root and package README files as AAI-only.
- Preserved evaluator scripts because AAI still calls them.

## Implemented in version `20260707T172000+0900`

- Added `runtime_logging.py` for detailed JSONL runtime traces, redacted environment snapshots, command start/end events, durations, return codes, and stdout/stderr artifacts.
- Added `codex_adapter.py` for Codex CLI configuration and execution.
- Added `start.py` for AAI campaign start with optional Codex configuration.
- Added CLI commands: `start`, `configure-codex`, `codex-status`, `write-codex-prompt`, and `run-codex-agent`.
- `configure-codex` stores model name, Codex binary, sandbox mode, timeout, and the API-key environment variable name in `.aai/codex_config.json`; it does not store the secret value.
- `run-codex-agent` runs `codex exec` against a prepared child workspace, writes `codex_agent_run.json`, captures Codex JSONL/stdout/stderr, and writes a final message artifact.
- `run-child-eval` writes runtime traces and redacted environment snapshots for pack/local/modal evaluator commands.

## Earlier implemented layers

- `20260707T171000+0900`: campaign memory updates into `harness-ledger.md` and `TRAPS.md`.
- `20260707T170312+0900`: campaign summary rollup.
- `20260707T165028+0900`: one-command child round orchestration.
- `20260707T164312+0900`: child evaluator runner.
- `20260707T163714+0900`: child workspace lifecycle, diff capture, and parent selection.
- `20260707T160734+0900`: initial AAI harness workflow layer.

## Non-goals

- AAI does not vendor the old full-agent trace package.
- AAI does not store API keys or access tokens in repo files.
- AAI does not allow child workers to modify evaluator scripts without proposal review.
- AAI does not make Codex responsible for global campaign control.

## Next engineering steps

1. Add a guarded `workflow-run` command that executes allowed actions end-to-end from the current workflow state.
2. Add `run-agent-round` on top of the hard workflow: plan, prepare, run executor, evaluate, gate, summarize, memory, population admit, select parent.
3. Add novelty/failure-aware parent selection from `population.py`, not only latency.
4. Add optional Claude Code and LoongFlow-compatible executor/planner adapters.
5. Add CI checks that validate workflow transitions and sample evidence gates.
