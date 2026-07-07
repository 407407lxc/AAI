# AAI Harness Workflow Layer

AAI is now designed as a **LoongFlow-style workflow control plane** with user-defined AAI workflow semantics. The old `full-agent/` traces are not vendored in this branch, but their useful architectural idea is preserved:

```text
Plan -> Execute -> Evaluate -> Summarize -> Checkpoint / Parent Selection
```

In AAI, that becomes:

```text
AAI hard workflow engine
  -> structured planner decision
  -> bounded executor backend such as Codex
  -> evaluator / gate / archive
  -> campaign summary
  -> memory + TRAPS
  -> population checkpoint / next parent
```

Codex is **not** the workflow owner. Codex is an executor backend for the bounded `run_agent` node.

## Core principle

AAI does not rely on prompt-only control.

- AAI owns the hard workflow state machine in `workflow.json`.
- Planner output is a structured artifact, not only a text prompt.
- Executor backends, such as Codex or future Claude Code / LoongFlow adapters, may only operate inside allowed workflow nodes.
- Evaluator, gate, archive, campaign memory, and parent selection stay under AAI control.
- Failed candidates are archived as negative evidence and can enter TRAPS.

## Main modules

```text
aai_harness/
  workflow.py        hard AAI state machine and allowed transitions
  planner.py         LoongFlow-style structured planner decision
  population.py      population/checkpoint database and lineage memory
  codex_adapter.py   Codex CLI executor backend
  child_eval.py      evaluator backend wrapper
  gates.py           promotion gate
  archive.py         variant/failed archive and ledger/TRAPS helpers
  summary.py         campaign rollup
  memory.py          long-term memory update
```

## Workflow states

The default AAI state machine is:

```text
TASK_RESOLVED
  -> BASELINE_READY
  -> ROUND_PLANNED
  -> CHILD_PREPARED
  -> AGENT_RAN
  -> EVALUATED
  -> GATED_ARCHIVED
  -> SUMMARIZED
  -> MEMORY_UPDATED
  -> PARENT_SELECTED
  -> ROUND_PLANNED
```

Mode 3 proposal review is represented as a separate guarded transition from memory-updated campaign state.

## Prerequisites

Run commands from `agent-assisted/` unless noted otherwise.

You need:

- Python environment that can import and run the evaluator scripts;
- Codex CLI installed and available as `codex` or another configured binary;
- an API key exported through an environment variable;
- Modal credentials and trace volume only when running `--mode modal-full`.

```bash
cd agent-assisted
export CODEX_API_KEY=<your OpenAI API key>
```

AAI stores the API-key environment variable name, not the secret value. Runtime environment snapshots redact variables whose names look like keys, tokens, secrets, passwords, auth values, or credentials.

## Quick start: workflow-controlled Codex round

### 1. Configure Codex

```bash
python -m aai_harness.cli configure-codex \
  --model gpt-5.5-codex \
  --api-key-env CODEX_API_KEY
```

Check the redacted status:

```bash
python -m aai_harness.cli codex-status
```

### 2. Start AAI and create the hard workflow

```bash
python -m aai_harness.cli start \
  --config-path <definition>/config.toml \
  --campaign-id campaign-demo \
  --codex-model gpt-5.5-codex
```

`start` now creates both campaign state and:

```text
.aai/campaigns/<campaign_id>/workflow.json
```

Check current state and allowed next actions:

```bash
python -m aai_harness.cli workflow-status \
  --campaign-id campaign-demo
```

### 3. Bootstrap baseline

```bash
python -m aai_harness.cli bootstrap \
  --config-path <definition>/config.toml \
  --version 20260707T175500+0900

python -m aai_harness.cli workflow-advance \
  --campaign-id campaign-demo \
  --action bootstrap_baseline \
  --artifact baseline_manifest=.aai/archive/<definition>/baseline/20260707T175500+0900/manifest.json
```

The explicit `workflow-advance` call records that Mode 0 completed and moves the hard workflow to `BASELINE_READY`.

### 4. Plan the next round

```bash
python -m aai_harness.cli plan-round \
  --campaign-id campaign-demo \
  --objective "Optimize the candidate solution while preserving correctness and evidence requirements." \
  --child-id child-0001
```

This writes:

```text
.aai/campaigns/<campaign_id>/plans/plan-<version>.json
.aai/campaigns/<campaign_id>/plans/plan-<version>.md
```

The JSON plan is the authoritative workflow artifact. It includes parent id, child ids, objective, constraints, executor backend, evaluator mode, memory inputs, and traps to avoid.

### 5. Prepare child workspace

```bash
python -m aai_harness.cli prepare-child \
  --campaign-id campaign-demo \
  --child-id child-0001 \
  --parent-id baseline \
  --config-path <definition>/config.toml

python -m aai_harness.cli workflow-advance \
  --campaign-id campaign-demo \
  --action prepare_child \
  --child-id child-0001 \
  --artifact child_json=.aai/campaigns/campaign-demo/children/child-0001/child.json
```

The child agent should edit only:

```text
.aai/campaigns/<campaign_id>/children/<child_id>/workspace/solution/
```

### 6. Run Codex as executor backend

```bash
python -m aai_harness.cli run-codex-agent \
  --campaign-id campaign-demo \
  --child-id child-0001 \
  --objective "Optimize the candidate solution while preserving correctness and evidence requirements."

python -m aai_harness.cli workflow-advance \
  --campaign-id campaign-demo \
  --action run_agent \
  --artifact agent_run_json=.aai/campaigns/campaign-demo/children/child-0001/codex_agent_run.json
```

Default invocation shape:

```text
codex exec --sandbox workspace-write --model <model> --json --ephemeral --output-last-message <path> <prompt>
```

### 7. Evaluate candidate

```bash
python -m aai_harness.cli run-child-eval \
  --campaign-id campaign-demo \
  --child-id child-0001 \
  --mode modal-full \
  --workers 10

python -m aai_harness.cli workflow-advance \
  --campaign-id campaign-demo \
  --action evaluate_child \
  --artifact child_eval_json=.aai/campaigns/campaign-demo/children/child-0001/child_eval.json \
  --artifact result_json=.aai/campaigns/campaign-demo/children/child-0001/result.json \
  --artifact diff_patch=.aai/campaigns/campaign-demo/children/child-0001/diff.patch
```

### 8. Gate and archive

```bash
python -m aai_harness.cli gate-archive \
  --evidence-json .aai/campaigns/campaign-demo/children/child-0001/result.json \
  --diff-patch .aai/campaigns/campaign-demo/children/child-0001/diff.patch \
  --kind variant

python -m aai_harness.cli workflow-advance \
  --campaign-id campaign-demo \
  --action gate_archive \
  --artifact gate_json=.aai/campaigns/campaign-demo/children/child-0001/gate.json \
  --artifact archive_manifest=<archive-manifest-path>
```

Promotion is controlled by AAI gates, not by Codex.

### 9. Summarize and update memory

```bash
python -m aai_harness.cli summarize-campaign --campaign-id campaign-demo
python -m aai_harness.cli workflow-advance \
  --campaign-id campaign-demo \
  --action summarize_campaign \
  --artifact campaign_summary_json=.aai/campaigns/campaign-demo/campaign_summary.json

python -m aai_harness.cli update-campaign-memory --campaign-id campaign-demo
python -m aai_harness.cli workflow-advance \
  --campaign-id campaign-demo \
  --action update_memory \
  --artifact memory_update_json=.aai/campaigns/campaign-demo/memory_update.json
```

### 10. Admit into population and select parent

```bash
python -m aai_harness.cli admit-population \
  --campaign-id campaign-demo \
  --child-id child-0001 \
  --definition <definition>

python -m aai_harness.cli population-status \
  --definition <definition>

python -m aai_harness.cli select-parent \
  --definition <definition>

python -m aai_harness.cli workflow-advance \
  --campaign-id campaign-demo \
  --action select_parent \
  --artifact selected_parent=.aai/archive/<definition>/selected-parent.json
```

The population database is LoongFlow-inspired: all archived variants and failures are admitted as lineage evidence, while only gated variants can become best members.

## Command reference for workflow additions

### `workflow-init`

Creates a hard workflow without running `start`.

```bash
python -m aai_harness.cli workflow-init \
  --campaign-id campaign-demo \
  --definition <definition> \
  --config-path <definition>/config.toml \
  --planner-backend rule \
  --executor-backend codex \
  --evaluator-backend modal-full
```

### `workflow-status`

Prints current state, allowed actions, current parent/child, and workflow invariants.

```bash
python -m aai_harness.cli workflow-status --campaign-id campaign-demo
```

### `workflow-advance`

Advances only along allowed transitions.

```bash
python -m aai_harness.cli workflow-advance \
  --campaign-id campaign-demo \
  --action plan_round \
  --artifact plan_json=<path>
```

If the action is not valid from the current state, AAI raises an error.

### `plan-round`

Writes a structured planner decision.

```bash
python -m aai_harness.cli plan-round \
  --campaign-id campaign-demo \
  --objective "next optimization objective" \
  --child-id child-0001
```

### `admit-population`

Adds one child round to the population/checkpoint database.

```bash
python -m aai_harness.cli admit-population \
  --campaign-id campaign-demo \
  --child-id child-0001 \
  --definition <definition>
```

### `population-status`

Shows population members, best member, and checkpoint paths.

```bash
python -m aai_harness.cli population-status --definition <definition>
```

## Runtime archive layout

```text
.aai/
  codex_config.json
  archive/<definition>/
    baseline/<version>/
    variants/variant-<version>/
    failed/failed-<version>/
    population/
      population.json
      checkpoints/checkpoint-<version>/
    selected-parent.json
    traps/TRAPS.md
    harness-ledger.md
  campaigns/<campaign_id>/
    workflow.json
    plans/plan-<version>.json
    plans/plan-<version>.md
    aai_start.json
    campaign.json
    campaign_summary.json
    campaign_summary.md
    memory_update.json
    children/<child_id>/
      child.json
      codex_agent_run.json
      child_eval.json
      round_report.json
      gate.json
      parent_solution/
      workspace/config.toml
      workspace/solution/
      runtime/
      diff.patch
      result.json
```

## Relationship to LoongFlow

AAI borrows the useful structure of the original full-agent design:

- planner consumes population / summaries / traps;
- executor spawns bounded child candidates;
- evaluator is the promotion gate;
- summarizer distills outcomes;
- checkpoint database preserves lineage and negative evidence.

But AAI replaces the workflow and implementation details with your AAI flow:

- draw.io stages become explicit workflow states;
- Codex is only an executor backend;
- AAI gates and archive memory are authoritative;
- target packages are external, not vendored historical kernels;
- LoongFlow can later be added as a planner/backend adapter, not as the whole base repository.
