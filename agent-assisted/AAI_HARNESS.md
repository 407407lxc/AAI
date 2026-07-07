# Agentic AI Infrastructure Harness Plan

This document records how the draw.io workflow maps onto the repository implementation.

## Core principle

AAI separates kernel search from harness governance:

- **Child worker**: edits a bounded candidate workspace, normally only `solution/`, and emits evidence.
- **Master campaign**: selects parents, writes narrow prompts, evaluates evidence, archives variants/failures, updates long-term memory, and decides whether the next round should continue.
- **Mode 3 proposal review**: allows harness changes only when repeated evidence shows a tooling gap.

This prevents reward hacking where a kernel-search agent modifies evaluator, baseline, hidden scoring, or archive memory to make itself look better.

## Workflow mapping

| Draw.io stage | Repository implementation |
| --- | --- |
| Stage -1: requirement parsing / feasibility | `aai_harness.schemas.TaskSpec`, `aai_harness.bootstrap.resolve_task` |
| Mode 0: build / deploy / first baseline | `aai_harness.bootstrap.bootstrap_baseline` |
| Stage 1: bounded child optimization | evidence schema in `aai_harness.schemas.EvidenceRecord`; gate checks in `aai_harness.gates` |
| Stage 2: Master Campaign | `aai_harness.campaign`, `aai_harness.archive` |
| Mode 3: evidence-backed harness proposal | `aai_harness.proposal` |

## Non-goals for this first implementation

- It does not replace LoongFlow.
- It does not replace FlashInfer-Bench or Modal evaluator scripts.
- It does not automatically call an LLM endpoint.
- It does not allow child workers to modify evaluator scripts without proposal review.

## Next engineering steps

1. Add a child workspace runner that copies a parent variant into `.aai/campaigns/<id>/children/<child>/workspace/`.
2. Add automatic `git diff` capture for each child workspace.
3. Add parent selection using archive score, novelty, and failure traps.
4. Add optional adapters for LoongFlow planner/executor outputs.
5. Add CI checks that run the gate on sample evidence.
