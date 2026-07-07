# Agentic AI Infrastructure Harness Plan

This document records how the draw.io workflow maps onto the repository implementation.

## Core principle

AAI separates kernel search from harness governance:

- **Child worker**: edits a bounded candidate workspace, normally only `solution/`, and emits evidence.
- **Master campaign**: selects parents, writes narrow prompts, evaluates evidence, archives variants/failures, updates long-term memory, and decides whether the next round should continue.
- **Mode 3 proposal review**: allows harness changes only when repeated evidence shows a tooling gap.

This prevents reward hacking where a kernel-search agent modifies evaluator, baseline, scoring, or archive memory to make itself look better.

## Workflow mapping

| Draw.io stage | Repository implementation |
| --- | --- |
| Stage -1: requirement parsing / feasibility | `aai_harness.schemas.TaskSpec`, `aai_harness.bootstrap.resolve_task` |
| Mode 0: build / deploy / first baseline | `aai_harness.bootstrap.bootstrap_baseline` |
| Stage 1: bounded child optimization | `aai_harness.workspace`, `aai_harness.diffing`, evidence schema in `aai_harness.schemas.EvidenceRecord`, gate checks in `aai_harness.gates` |
| Stage 2: Master Campaign | `aai_harness.campaign`, `aai_harness.archive`, `aai_harness.parent_selection` |
| Mode 3: evidence-backed harness proposal | `aai_harness.proposal` |

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

1. Add automatic evaluator invocation from inside a child workspace.
2. Add parent selection using novelty and failure traps, not only latency metric.
3. Add optional adapters for LoongFlow planner/executor outputs.
4. Add CI checks that run the gate on sample evidence.
5. Add campaign-level rollup summaries across children and archived variants.
