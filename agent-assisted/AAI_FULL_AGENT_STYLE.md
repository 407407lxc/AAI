# AAI Full-Agent-Style Implementation Notes

This document explains how AAI now mirrors the original `full-agent/` design while keeping the user-designed AAI workflow as the source of truth.

## Reference full-agent structure

The original `full-agent/` package preserved the full autonomous search history:

```text
planner / executor / evaluator / summarizer I/O
population snapshots
per-evaluation logs
```

Its trace schema had three major subtrees:

```text
database/checkpoints/checkpoint-checkpoint-iter-{K}-{N}/
iteration/{K}/planner/
iteration/{K}/executor/{M_N}/
iteration/{K}/summarizer/
evaluator/eval_<hash>/
```

AAI should imitate this structure because it makes agent campaigns auditable, resumable, and easy for future agents to understand.

## What AAI copies from full-agent

AAI copies the architectural pattern:

```text
Planner -> Executor -> Evaluator -> Summarizer -> Checkpoint / Parent Selection
```

AAI also mirrors the trace layout:

```text
.aai/campaigns/<campaign_id>/full_agent_trace/
  database/
    checkpoints/
      checkpoint-iter-<K>-<child_id>/
        checkpoint.json
        metadata.json
        selected-parent.json
        best_solution/
        best_solution.json
        round_report.json
    solutions/
  iteration/
    <K>/
      planner/
        plan.json
        plan.md
      executor/
        <child_id>/
          child.json
          prompt.md
          agent_run.json
          ITERATIONS.md
          trajectory.json
          audit.json
          diff.patch
          candidate_solution/
      summarizer/
        campaign_summary.json
        summary.md
        memory_update.json
        workflow.json
  evaluator/
    eval_<hash>/
      child_eval.json
      result.json
      round_report.json
      gate.json
      solution.json
      benchmark_detailed_results.json
      evaluation_process.log
      logs/
  trace_index.json
```

## What AAI intentionally changes

AAI does not restore or vendor old full-agent traces. Instead:

- `workflow.json` is the authoritative control artifact.
- `plan-<version>.json` is the authoritative planner decision.
- Codex / Claude Code / LoongFlow-compatible runners are executor backends.
- AAI gates and archive manifests control promotion.
- AAI population/checkpoint memory preserves lineage.
- Full-agent-style trace is a mirror/export layer for auditability and handoff.

## Implementation

New module:

```text
aai_harness/full_agent_trace.py
```

New module CLI:

```text
aai_harness/full_agent_trace_cli.py
```

Commands:

```bash
python -m aai_harness.full_agent_trace_cli init \
  --campaign-id campaign-demo \
  --definition <definition> \
  --objective "latency optimization"

python -m aai_harness.full_agent_trace_cli sync \
  --campaign-id campaign-demo \
  --definition <definition> \
  --iteration 1 \
  --child-id child-0001

python -m aai_harness.full_agent_trace_cli status \
  --campaign-id campaign-demo

python -m aai_harness.full_agent_trace_cli tree \
  --campaign-id campaign-demo
```

## Recommended usage in AAI flow

After a round reaches at least `GATED_ARCHIVED`, run:

```bash
python -m aai_harness.full_agent_trace_cli sync \
  --campaign-id campaign-demo \
  --definition <definition> \
  --iteration 1 \
  --child-id child-0001
```

For a completed round, the sync command mirrors:

- latest planner artifact into `iteration/<K>/planner/`;
- child executor artifacts into `iteration/<K>/executor/<child_id>/`;
- evaluation/gate/archive artifacts into `evaluator/eval_<hash>/`;
- summary/memory/workflow artifacts into `iteration/<K>/summarizer/`;
- population / selected parent / best solution evidence into `database/checkpoints/`.

## Source of truth rule

The full-agent-style trace is a handoff and audit mirror. It should not become the primary state machine.

Source of truth remains:

```text
workflow.json
plans/plan-<version>.json
children/<child_id>/result.json
children/<child_id>/gate.json
children/<child_id>/round_report.json
archive/<definition>/population/population.json
archive/<definition>/harness-ledger.md
archive/<definition>/traps/TRAPS.md
```

## Future work

1. Integrate full-agent-style sync into `run-agent-round` once that workflow-aware runner exists.
2. Add optional exact LoongFlow adapter for planner/executor backends.
3. Add a trace validator that checks full-agent-style mirror completeness.
4. Make `iteration` derive from workflow event count or campaign round id instead of being manually supplied.
5. Add tests that compare AAI trace layout with the documented original full-agent schema.
