# AAI Harness Workflow Layer

This package implements the Agentic AI Infrastructure (AAI) harness layer for the FlashInfer contest package. It wraps the existing `agent-assisted/scripts/` evaluation tools instead of replacing them.

The design follows the uploaded draw.io workflow:

1. **Stage -1 — task parsing / feasibility**: resolve `config.toml`, solution directory, runtime, hardware, metrics, quality gates, and credential policy.
2. **Mode 0 — bootstrap build / first baseline**: validate the target, pack the current solution, snapshot config/source, optionally run a local baseline, and write immutable baseline evidence.
3. **Stage 1 — bounded child optimization**: child workers edit an isolated candidate workspace and emit `ITERATIONS.md`, `trajectory.json`, `result.json`, `diff.patch`, stdout/stderr logs, and audit findings.
4. **Stage 2 — Master Campaign**: master reads archive memory, selects parent, writes a narrow prompt, gates evidence, archives variants or failures, updates long-term memory, and summarizes campaign state.
5. **Mode 3 — harness proposal review**: harness changes require evidence-backed `PROPOSALS.md` and master review.

## Invocation

Run commands from `agent-assisted/`:

```bash
export CODEX_API_KEY=<your OpenAI API key>

python -m aai_harness.cli configure-codex \
  --model gpt-5.5-codex \
  --api-key-env CODEX_API_KEY

python -m aai_harness.cli start \
  --config-path gdn_decode_qk4_v8_d128_k_last/config.toml \
  --campaign-id campaign-20260707T172000+0900 \
  --codex-model gpt-5.5-codex

python -m aai_harness.cli prepare-child \
  --campaign-id campaign-20260707T172000+0900 \
  --child-id child-0001 \
  --parent-id baseline \
  --config-path gdn_decode_qk4_v8_d128_k_last/config.toml

python -m aai_harness.cli run-codex-agent \
  --campaign-id campaign-20260707T172000+0900 \
  --child-id child-0001 \
  --objective "Optimize the candidate solution while preserving correctness and evidence requirements."

python -m aai_harness.cli run-child-round \
  --campaign-id campaign-20260707T172000+0900 \
  --child-id child-0001 \
  --parent-id baseline \
  --config-path gdn_decode_qk4_v8_d128_k_last/config.toml \
  --mode modal-full \
  --workers 10 \
  --kind variant
```

From the repository root, prefix the command with `PYTHONPATH=agent-assisted`:

```bash
PYTHONPATH=agent-assisted python -m aai_harness.cli --help
```

## Timestamp versions

All persistent AAI records use timestamp versions in the form:

```text
YYYYMMDDTHHMMSS+ZZZZ
```

Example:

```text
20260707T172000+0900
```

This is used for bootstrap baselines, archived variants, failed runs, proposal files, child workspaces, campaign summaries, memory updates, runtime logs, and harness ledgers.

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

`.aai/` is intended for reproducible campaign evidence. Do not archive secrets or raw credentials.

## Codex adapter

AAI can use OpenAI Codex CLI as its child agent backend. Configure it once:

```bash
export CODEX_API_KEY=<your OpenAI API key>
python -m aai_harness.cli configure-codex --model gpt-5.5-codex --api-key-env CODEX_API_KEY
python -m aai_harness.cli codex-status
```

`configure-codex` writes `.aai/codex_config.json`; it records the environment variable name, not the secret value. Runtime logs redact environment variables whose names look like keys, tokens, secrets, passwords, or credentials.

The default adapter invokes Codex through non-interactive mode:

```text
codex exec --sandbox workspace-write --model <model> --json --ephemeral --output-last-message <path> <prompt>
```

If your installed Codex CLI uses different flags, pass `--command-template` to `configure-codex` and use placeholders such as `{codex_bin}`, `{model}`, `{sandbox}`, `{prompt}`, `{prompt_path}`, and `{final_message_path}`.

## Child workspace lifecycle

A child workspace starts from a parent snapshot and creates a mutable candidate copy. The worker edits only the workspace solution copy:

```text
.aai/campaigns/<campaign_id>/children/<child_id>/workspace/solution/
```

`run-codex-agent` writes `codex_agent_run.json`, Codex JSONL/stdout/stderr logs, a final message file, and a runtime trace. `run-child-round` remains the high-level evaluator/archive command after the Codex-backed child has produced a candidate.

Use `--mode pack` for smoke tests. Use `--mode modal-full` for promotion-quality evidence.

## Campaign summary and memory

`summarize-campaign` reads all child `round_report.json` files and writes:

- `campaign_summary.json`: machine-readable counters, child rows, best metric, gate failure codes, and recommended next steps.
- `campaign_summary.md`: human-readable campaign dashboard.

`update-campaign-memory` then appends summary findings to the long-term archive memory:

- `archive/<definition>/harness-ledger.md`: compact campaign summary and recommended next steps.
- `archive/<definition>/traps/TRAPS.md`: repeated gate failures and failed child statuses that should be avoided in later rounds.

The command writes `memory_update.json` under the campaign directory so the memory mutation itself is auditable.

## Runtime logging

Every Codex agent and child evaluator process gets a runtime directory containing:

- `runtime_trace.jsonl`: append-only structured events, command start/end, return codes, durations, and artifact paths.
- `environment.json`: redacted environment and platform snapshot.
- `commands/*.stdout.log` and `commands/*.stderr.log`: raw command output for debugging.

The evaluator also mirrors command stdout/stderr into the existing child `logs/` directory for backwards compatibility.

## Gate policy

The default archive gate checks for failed benchmark status, protected path edits, suspicious diff patterns, incomplete evidence, and evidence schema compatibility. Warnings are emitted for edits outside the default `solution/` scope. Errors block promotion as a variant.

## Relationship to existing scripts

The existing scripts remain the evaluator source of truth:

- `scripts/pack_solution.py`
- `scripts/run_local.py`
- `scripts/run_modal_single.py`
- `scripts/run_modal_multiple_gpus.py`

AAI harness code calls these scripts and standardizes evidence, gates, archive layout, campaign state, workspace isolation, Codex execution, diff capture, child evaluation, child-round orchestration, campaign summaries, memory updates, runtime logs, and proposal review around them.
