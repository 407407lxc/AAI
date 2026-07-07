# AAI Harness Workflow Layer

This package implements the Agentic AI Infrastructure (AAI) harness layer for the FlashInfer contest package. It wraps the existing `agent-assisted/scripts/` evaluation tools instead of replacing them.

The design follows the uploaded draw.io workflow:

1. **Stage -1 — task parsing / feasibility**: resolve `config.toml`, solution directory, runtime, hardware, metrics, quality gates, and credential policy.
2. **Mode 0 — bootstrap build / first baseline**: validate the target, pack the current solution, snapshot config/source, optionally run a local baseline, and write immutable baseline evidence.
3. **Stage 1 — bounded child optimization**: child workers may edit only `solution/` or explicitly approved safety config, then must emit evidence: `ITERATIONS.md`, `trajectory.json`, `result.json`, `diff.patch`, stdout/stderr logs, and audit findings.
4. **Stage 2 — Master Campaign**: master reads archive memory, selects parent, writes a narrow prompt, spawns child work, gates evidence, archives variants or failures, and updates long-term memory.
5. **Mode 3 — harness proposal review**: harness changes require evidence-backed `PROPOSALS.md` and master review. Child workers should not directly change evaluator, baseline, hidden scoring, or campaign memory.

## Invocation

Run commands from `agent-assisted/`:

```bash
python -m aai_harness.cli init \
  --config-path gdn_decode_qk4_v8_d128_k_last/config.toml \
  --campaign-id campaign-20260707T160734+0900

python -m aai_harness.cli bootstrap \
  --config-path gdn_decode_qk4_v8_d128_k_last/config.toml \
  --version 20260707T160734+0900

python -m aai_harness.cli campaign-init \
  --definition gdn_decode_qk4_v8_d128_k_last \
  --campaign-id campaign-20260707T160734+0900

python -m aai_harness.cli proposal-template \
  --campaign-id campaign-20260707T160734+0900
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
20260707T160734+0900
```

This is used for bootstrap baselines, archived variants, failed runs, proposal files, and harness ledgers.

## Runtime archive layout

The CLI writes runtime state under `agent-assisted/.aai/`:

```text
.aai/
  archive/<definition>/
    baseline/<version>/
    variants/variant-<version>/
    failed/failed-<version>/
    traps/TRAPS.md
    harness-ledger.md
  campaigns/<campaign_id>/
    campaign.json
    children/
    prompts/
    proposals/
    logs/
```

`.aai/` is intended for reproducible campaign evidence. Do not archive secrets or raw credentials.

## Gate policy

The default archive gate checks for:

- failed workloads or failed run status;
- protected path edits such as baselines, reference data, trace data, or evaluator scripts;
- suspicious hidden-eval / leaderboard / hardcoded UUID patterns in candidate diffs;
- missing or incompatible evidence schema.

Warnings are emitted for edits outside the default `solution/` scope. Errors block promotion/archive-as-variant.

## Relationship to existing scripts

The existing scripts remain the evaluator source of truth:

- `scripts/pack_solution.py`
- `scripts/run_local.py`
- `scripts/run_modal_single.py`
- `scripts/run_modal_multiple_gpus.py`

AAI harness code calls these scripts and standardizes evidence, gates, archive layout, campaign state, and proposal review around them.
