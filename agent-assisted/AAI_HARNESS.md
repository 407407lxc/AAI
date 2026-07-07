# Agentic AI Infrastructure Harness Plan

This document records how the draw.io workflow maps onto the repository implementation.

## Core principle

AAI separates kernel search from harness governance:

- **Child worker**: edits a bounded candidate workspace, normally only `solution/`, and emits evidence.
- **Master campaign**: selects parents, writes narrow prompts, evaluates evidence, archives variants/failures, updates long-term memory, summarizes campaign state, writes memory updates, and decides whether the next round should continue.
- **Mode 3 proposal review**: allows harness changes only when repeated evidence shows a tooling gap.

This prevents reward hacking where a kernel-search agent modifies evaluator, baseline, scoring, or archive memory to make itself look better.

## Workflow mapping

| Draw.io stage | Repository implementation |
| --- | --- |
| Stage -1: requirement parsing / feasibility | `aai_harness.schemas.TaskSpec`, `aai_harness.bootstrap.resolve_task` |
| Mode 0: build / deploy / first baseline | `aai_harness.bootstrap.bootstrap_baseline` |
| Stage 1: bounded child optimization | `aai_harness.workspace`, `aai_harness.diffing`, `aai_harness.child_eval`, `aai_harness.round`, evidence schema in `aai_harness.schemas.EvidenceRecord`, gate checks in `aai_harness.gates` |
| Stage 2: Master Campaign | `aai_harness.campaign`, `aai_harness.archive`, `aai_harness.parent_selection`, `aai_harness.summary`, `aai_harness.memory` |
| Mode 3: evidence-backed harness proposal | `aai_harness.proposal` |

## Implemented in version `20260707T171000+0900`

- Added `memory.py` for long-term campaign memory updates.
- Added `update-campaign-memory` CLI command.
- The command reads or creates `campaign_summary.json` / `campaign_summary.md`.
- It appends compact campaign summary entries and recommended next steps into `archive/<definition>/harness-ledger.md`.
- It writes repeated gate failures and failed child statuses into `archive/<definition>/traps/TRAPS.md`.
- It writes `memory_update.json` under the campaign directory so the memory mutation is auditable.

## Implemented in version `20260707T170312+0900`

- Added `summary.py` for campaign rollup.
- Added `summarize-campaign` CLI command.
- The summary command reads all child `round_report.json` files under a campaign.
- It writes `campaign_summary.json` for machine-readable state and `campaign_summary.md` for human review.
- It reports child counts, gate pass counts, archive-kind counts, status/mode counts, repeated gate failure codes, best child by metric, and recommended next steps.

## Implemented in version `20260707T165028+0900`

- Added `round.py` for one-command child round orchestration.
- Added `run-child-round` CLI command.
- The round command runs prepare, eval, gate, archive, and writes `round_report.json`.
- Gate failures are preserved as failed evidence instead of disappearing.
- The high-level command keeps low-level commands available for debugging.

## Implemented in version `20260707T164312+0900`

- Added `child_eval.py` for pack/local/modal-full evaluation of a child workspace.
- Added `run-child-eval` CLI command.
- `run-child-eval` writes `child_eval.json`, captures process logs, refreshes `diff.patch`, and finalizes `result.json` unless `--no-finalize` is used.
- The runner points existing evaluator scripts at `workspace/config.toml` and `workspace/solution`, keeping repository-level submitted solutions unchanged.

## Implemented in version `20260707T163714+0900`

- Added child workspace preparation under `.aai/campaigns/<campaign_id>/children/<child_id>/`.
- Added immutable parent solution snapshot plus mutable candidate solution copy.
- Added placeholder `ITERATIONS.md`, `trajectory.json`, and `audit.json` creation for every child.
- Added directory diff capture to produce `diff.patch` from parent snapshot vs candidate workspace.
- Added child evidence finalization into the shared `EvidenceRecord` schema.
- Added simple parent selection over archived baselines and variants.

## Non-goals for this first implementation

- It does not replace LoongFlow.
- It does not replace FlashInfer-Bench or Modal evaluator scripts.
- It does not automatically call an LLM endpoint.
- It does not allow child workers to modify evaluator scripts without proposal review.

## Next engineering steps

1. Add parent selection using novelty and failure traps, not only latency metric.
2. Add optional adapters for LoongFlow planner/executor outputs.
3. Add CI checks that run the gate on sample evidence.
4. Add promotion helpers that copy a gated variant into an explicit release candidate directory.
5. Add memory-aware child prompt generation that injects recent TRAPS into each round prompt.
