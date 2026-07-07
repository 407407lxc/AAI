# AAI Harness Workflow Layer

This package implements the Agentic AI Infrastructure (AAI) harness layer. It is now AAI-only: historical retained kernels, legacy agent skills, reports, and full-agent traces are not vendored in this branch.

AAI expects a target package to be provided through a `config.toml` path:

```text
<definition>/config.toml
```

The target package supplies the solution directory and entry point consumed by the evaluator scripts.

## What AAI provides

- Codex-backed child-agent execution.
- Isolated child workspaces.
- Detailed runtime traces for debugging.
- Evaluator wrappers around pack/local/Modal scripts.
- Evidence schemas and archive gates.
- Variant/failed archival.
- Campaign summaries.
- Long-term memory through `harness-ledger.md` and `TRAPS.md`.
- Mode 3 evidence-backed proposal review for harness changes.

## Prerequisites

Run commands from `agent-assisted/` unless noted otherwise.

You need:

- Python environment that can import and run the evaluator scripts;
- Codex CLI installed and available as `codex` or another configured binary;
- an API key exported through an environment variable;
- Modal credentials and trace volume only when running `--mode modal-full`.

Example:

```bash
cd agent-assisted
export CODEX_API_KEY=<your OpenAI API key>
```

AAI stores the API-key environment variable name, not the secret value. Runtime environment snapshots redact variables whose names look like keys, tokens, secrets, passwords, auth values, or credentials.

## Quick start: Codex-backed AAI round

This is the normal startup flow when using Codex as the AAI child agent.

```bash
cd agent-assisted
export CODEX_API_KEY=<your OpenAI API key>
```

### 1. Configure Codex

```bash
python -m aai_harness.cli configure-codex \
  --model gpt-5.5-codex \
  --api-key-env CODEX_API_KEY
```

This writes:

```text
.aai/codex_config.json
```

It records the model name, Codex binary, sandbox mode, timeout, and API-key environment variable name. It does not record the API key itself.

Check the redacted status:

```bash
python -m aai_harness.cli codex-status
```

Expected useful fields:

```text
api_key_present: True
model: gpt-5.5-codex
codex_bin: codex
sandbox: workspace-write
```

### 2. Start AAI

```bash
python -m aai_harness.cli start \
  --config-path <definition>/config.toml \
  --campaign-id campaign-demo \
  --codex-model gpt-5.5-codex
```

This resolves the target task, initializes the `.aai/` layout, initializes the campaign, optionally writes Codex config, and emits:

```text
.aai/campaigns/<campaign_id>/aai_start.json
.aai/campaigns/<campaign_id>/runtime/start-<version>/runtime_trace.jsonl
.aai/campaigns/<campaign_id>/runtime/start-<version>/environment.json
```

If the API key environment variable is missing, the start report will say `READY_NO_CODEX_KEY` instead of failing silently.

### 3. Bootstrap baseline evidence

```bash
python -m aai_harness.cli bootstrap \
  --config-path <definition>/config.toml \
  --version 20260707T174000+0900
```

This validates the target config, packs the current solution through `scripts/pack_solution.py`, snapshots config/source, and writes baseline evidence under:

```text
.aai/archive/<definition>/baseline/<version>/
```

Use `--run-local` only when `FIB_DATASET_PATH` is set and local CUDA evaluation is available.

### 4. Prepare a child workspace

```bash
python -m aai_harness.cli prepare-child \
  --campaign-id campaign-demo \
  --child-id child-0001 \
  --parent-id baseline \
  --config-path <definition>/config.toml
```

This creates:

```text
.aai/campaigns/<campaign_id>/children/<child_id>/
  child.json
  parent_solution/
  workspace/
    config.toml
    solution/
  ITERATIONS.md
  trajectory.json
  audit.json
```

The child agent should edit only:

```text
.aai/campaigns/<campaign_id>/children/<child_id>/workspace/solution/
```

### 5. Run Codex against the child workspace

```bash
python -m aai_harness.cli run-codex-agent \
  --campaign-id campaign-demo \
  --child-id child-0001 \
  --objective "Optimize the candidate solution while preserving correctness and evidence requirements."
```

This generates a Codex prompt if one is not provided, runs Codex non-interactively, and writes:

```text
children/<child_id>/codex_prompt.md
children/<child_id>/codex_agent_run.json
children/<child_id>/runtime/codex-<version>/runtime_trace.jsonl
children/<child_id>/runtime/codex-<version>/environment.json
children/<child_id>/runtime/codex-<version>/commands/codex_exec.stdout.log
children/<child_id>/runtime/codex-<version>/commands/codex_exec.stderr.log
children/<child_id>/runtime/codex-<version>/codex_final_message.md
```

Default invocation shape:

```text
codex exec --sandbox workspace-write --model <model> --json --ephemeral --output-last-message <path> <prompt>
```

If your installed Codex CLI uses different flags, configure a custom template:

```bash
python -m aai_harness.cli configure-codex \
  --model gpt-5.5-codex \
  --api-key-env CODEX_API_KEY \
  --command-template "codex exec --json --sandbox {sandbox} --model {model} --output-last-message {final_message_path} {prompt}"
```

Supported template placeholders:

```text
{codex_bin}
{model}
{sandbox}
{prompt}
{prompt_path}
{final_message_path}
```

### 6. Evaluate, gate, and archive the Codex candidate

Important: after `run-codex-agent`, use `--skip-prepare` so the Codex-modified workspace is not overwritten.

```bash
python -m aai_harness.cli run-child-round \
  --campaign-id campaign-demo \
  --child-id child-0001 \
  --parent-id baseline \
  --config-path <definition>/config.toml \
  --mode modal-full \
  --workers 10 \
  --kind variant \
  --skip-prepare
```

This runs the evaluator, refreshes `diff.patch`, writes `result.json`, writes `gate.json`, archives the run as a variant if the gate passes, otherwise archives it as failed evidence, and writes:

```text
children/<child_id>/child_eval.json
children/<child_id>/round_report.json
children/<child_id>/gate.json
children/<child_id>/diff.patch
children/<child_id>/result.json
```

For a cheap smoke test, use `--mode pack`. `pack` mode verifies packaging but does not produce promotion-quality benchmark evidence. The gate normally blocks it from becoming a variant and archives it as failed evidence.

### 7. Summarize campaign state

```bash
python -m aai_harness.cli summarize-campaign \
  --campaign-id campaign-demo
```

This scans all child `round_report.json` files and writes:

```text
.aai/campaigns/<campaign_id>/campaign_summary.json
.aai/campaigns/<campaign_id>/campaign_summary.md
```

The summary includes child counts, gate pass counts, archived variants, archived failures, status counts, mode counts, repeated gate failure codes, best child by metric, and recommended next steps.

### 8. Update long-term campaign memory

```bash
python -m aai_harness.cli update-campaign-memory \
  --campaign-id campaign-demo
```

This appends campaign findings into:

```text
.aai/archive/<definition>/harness-ledger.md
.aai/archive/<definition>/traps/TRAPS.md
```

It also writes:

```text
.aai/campaigns/<campaign_id>/memory_update.json
```

Use this when you want the next round to benefit from the previous round's failures, traps, and recommended next steps.

### 9. Select the next parent

```bash
python -m aai_harness.cli select-parent \
  --definition <definition>
```

This selects the best archived baseline/variant by the configured metric, defaulting to `avg_latency_ms`.

## Full command reference

### `configure-codex`

Writes `.aai/codex_config.json`.

```bash
python -m aai_harness.cli configure-codex \
  --model gpt-5.5-codex \
  --api-key-env CODEX_API_KEY \
  --codex-bin codex \
  --sandbox workspace-write \
  --timeout 7200
```

Use it when setting up Codex for the first time or changing model / binary / sandbox / timeout.

### `codex-status`

Prints redacted Codex config state.

```bash
python -m aai_harness.cli codex-status
```

Use it to confirm whether the API-key environment variable is present without exposing the key.

### `start`

Initializes an AAI campaign and optionally configures Codex.

```bash
python -m aai_harness.cli start \
  --config-path <definition>/config.toml \
  --campaign-id <campaign-id> \
  --codex-model <model-name>
```

Use it as the main entrypoint for a new AAI campaign.

### `bootstrap`

Creates immutable baseline evidence for the current target solution.

```bash
python -m aai_harness.cli bootstrap \
  --config-path <definition>/config.toml \
  --version <timestamp-version>
```

Use it before optimization so later variants have a baseline to compare against.

### `campaign-init`

Creates only campaign state.

```bash
python -m aai_harness.cli campaign-init \
  --definition <definition> \
  --campaign-id <campaign-id>
```

Usually `start` is preferred because it also resolves the task and can configure Codex.

### `prepare-child`

Creates an isolated child workspace.

```bash
python -m aai_harness.cli prepare-child \
  --campaign-id <campaign-id> \
  --child-id <child-id> \
  --parent-id <parent-id> \
  --config-path <definition>/config.toml
```

Use it before running Codex or manually editing a candidate.

### `write-codex-prompt`

Writes a prompt file without running Codex.

```bash
python -m aai_harness.cli write-codex-prompt \
  --campaign-id <campaign-id> \
  --child-id <child-id> \
  --objective "<objective>"
```

Use it for review/debugging or if another runner will invoke Codex manually.

### `run-codex-agent`

Runs Codex against a prepared child workspace.

```bash
python -m aai_harness.cli run-codex-agent \
  --campaign-id <campaign-id> \
  --child-id <child-id> \
  --objective "<objective>"
```

Use it to let Codex edit `workspace/solution/` and produce agent runtime artifacts.

### `run-child-eval`

Runs evaluator scripts against an existing child workspace without archiving.

```bash
python -m aai_harness.cli run-child-eval \
  --campaign-id <campaign-id> \
  --child-id <child-id> \
  --mode pack
```

Modes:

- `pack`: run `scripts/pack_solution.py` only;
- `local`: run pack, then `scripts/run_local.py` if `FIB_DATASET_PATH` is set;
- `modal-full`: run pack, then `scripts/run_modal_multiple_gpus.py`.

Use it when debugging evaluation separately from archival.

### `run-child-round`

Runs evaluate → gate → archive for one child round. It can also prepare the workspace, but after Codex has edited a workspace, pass `--skip-prepare`.

```bash
python -m aai_harness.cli run-child-round \
  --campaign-id <campaign-id> \
  --child-id <child-id> \
  --parent-id <parent-id> \
  --config-path <definition>/config.toml \
  --mode modal-full \
  --kind variant \
  --skip-prepare
```

Use it to turn a candidate into archived evidence.

### `diff-child`

Refreshes `diff.patch` between `parent_solution/` and `workspace/solution/`.

```bash
python -m aai_harness.cli diff-child \
  --campaign-id <campaign-id> \
  --child-id <child-id>
```

Use it when inspecting a candidate before evaluation.

### `finalize-child`

Writes `result.json` from child artifacts without archiving.

```bash
python -m aai_harness.cli finalize-child \
  --campaign-id <campaign-id> \
  --child-id <child-id>
```

Use it for manual/debug workflows.

### `gate`

Runs archive gate checks and writes `gate.json`.

```bash
python -m aai_harness.cli gate \
  --evidence-json <path-to-result.json> \
  --diff-patch <path-to-diff.patch>
```

Use it to validate evidence before promotion.

### `archive` and `gate-archive`

Archive existing evidence.

```bash
python -m aai_harness.cli gate-archive \
  --evidence-json <path-to-result.json> \
  --diff-patch <path-to-diff.patch> \
  --kind variant
```

Use `gate-archive` for normal workflows; use `archive` only when a gate result already exists.

### `summarize-campaign`

Writes campaign dashboard artifacts.

```bash
python -m aai_harness.cli summarize-campaign \
  --campaign-id <campaign-id> \
  --metric avg_latency_ms
```

Use it after one or more child rounds.

### `update-campaign-memory`

Appends summary findings into long-term memory.

```bash
python -m aai_harness.cli update-campaign-memory \
  --campaign-id <campaign-id> \
  --min-failure-count 1
```

Options:

- `--definition`: provide definition manually if it cannot be inferred;
- `--min-failure-count`: only write traps seen at least this many times;
- `--no-traps`: update only `harness-ledger.md`.

### `select-parent`

Selects the best archived parent.

```bash
python -m aai_harness.cli select-parent \
  --definition <definition> \
  --metric avg_latency_ms
```

Use it before starting the next child round.

### `proposal-template` and `review-proposal`

Mode 3 harness-change workflow.

```bash
python -m aai_harness.cli proposal-template --campaign-id <campaign-id>
python -m aai_harness.cli review-proposal --proposal <path-to-proposal.md>
```

Use these only when evidence shows the harness itself needs changes.

## Runtime archive layout

The CLI writes runtime state under `agent-assisted/.aai/`:

```text
.aai/
  codex_config.json
  archive/<definition>/
    baseline/<version>/
    variants/variant-<version>/
    failed/failed-<version>/
    selected-parent.json
    traps/TRAPS.md
    harness-ledger.md
  campaigns/<campaign_id>/
    aai_start.json
    campaign.json
    campaign_summary.json
    campaign_summary.md
    memory_update.json
    runtime/
      start-<version>/
        runtime_trace.jsonl
        environment.json
    children/<child_id>/
      child.json
      codex_prompt.md
      codex_agent_run.json
      child_eval.json
      round_report.json
      gate.json
      parent_solution/
      workspace/
        config.toml
        solution/
      logs/
      runtime/
        codex-<version>/
          runtime_trace.jsonl
          environment.json
          commands/
        eval-<version>/
          runtime_trace.jsonl
          environment.json
          commands/
      solution.json
      benchmark_detailed_results.json
      retained_run.log
      ITERATIONS.md
      trajectory.json
      audit.json
      diff.patch
      result.json
    prompts/
    proposals/
```

## Runtime logging

Every Codex agent and child evaluator process gets a runtime directory containing:

- `runtime_trace.jsonl`: append-only structured events, command start/end, return codes, durations, and artifact paths;
- `environment.json`: redacted environment and platform snapshot;
- `commands/*.stdout.log` and `commands/*.stderr.log`: raw command output for debugging.

The evaluator also mirrors command stdout/stderr into the existing child `logs/` directory for backwards compatibility.

## Gate policy

The default archive gate checks for failed benchmark status, protected path edits, suspicious diff patterns, incomplete evidence, and evidence schema compatibility. Warnings are emitted for edits outside the default `solution/` scope. Errors block promotion as a variant.

## Relationship to evaluator scripts

AAI keeps using these existing evaluator scripts as backends:

- `scripts/pack_solution.py`
- `scripts/run_local.py`
- `scripts/run_modal_single.py`
- `scripts/run_modal_multiple_gpus.py`

AAI harness code calls these scripts and standardizes evidence, gates, archive layout, campaign state, workspace isolation, Codex execution, diff capture, child evaluation, child-round orchestration, campaign summaries, memory updates, runtime logs, and proposal review around them.
