# Agentic AI Infrastructure Harness Package

This directory contains the AAI harness package and the evaluator scripts that the harness can call.

The old retained-kernel directories, old agent workflow skills, historical report PDF, and full-agent trace package have been removed from this branch. AAI does not need to vendor those artifacts. Instead, AAI expects a target package to be supplied through a `config.toml` path such as:

```text
<definition>/config.toml
```

The target package should provide the solution directory and entry point expected by the existing evaluator scripts.

## Layout

```text
.
|-- README.md
|-- AAI_HARNESS.md
|-- scripts/
`-- aai_harness/
```

Important paths:

- `aai_harness/`: AAI harness Python package, CLI, Codex adapter, runtime logging, archive gates, campaign summary, and memory update logic.
- `scripts/`: existing pack/local/Modal evaluator scripts that AAI uses for candidate evaluation.
- `AAI_HARNESS.md`: design note mapping the AAI workflow to the implementation modules.

## Codex-backed quick start

Run from this directory:

```bash
export CODEX_API_KEY=<your OpenAI API key>

python -m aai_harness.cli configure-codex \
  --model gpt-5.5-codex \
  --api-key-env CODEX_API_KEY

python -m aai_harness.cli start \
  --config-path <definition>/config.toml \
  --campaign-id campaign-demo \
  --codex-model gpt-5.5-codex

python -m aai_harness.cli bootstrap \
  --config-path <definition>/config.toml \
  --version 20260707T174000+0900

python -m aai_harness.cli prepare-child \
  --campaign-id campaign-demo \
  --child-id child-0001 \
  --parent-id baseline \
  --config-path <definition>/config.toml

python -m aai_harness.cli run-codex-agent \
  --campaign-id campaign-demo \
  --child-id child-0001 \
  --objective "Optimize the candidate solution while preserving correctness and evidence requirements."

python -m aai_harness.cli run-child-round \
  --campaign-id campaign-demo \
  --child-id child-0001 \
  --parent-id baseline \
  --config-path <definition>/config.toml \
  --mode modal-full \
  --workers 10 \
  --kind variant \
  --skip-prepare

python -m aai_harness.cli summarize-campaign --campaign-id campaign-demo
python -m aai_harness.cli update-campaign-memory --campaign-id campaign-demo
python -m aai_harness.cli select-parent --definition <definition>
```

Important: after `run-codex-agent`, pass `--skip-prepare` to `run-child-round`; otherwise the child workspace is recreated and the Codex candidate can be overwritten.

## Command meanings

- `configure-codex`: records Codex model, binary, sandbox, timeout, and API-key environment variable name in `.aai/codex_config.json`; it does not store the API key.
- `codex-status`: prints redacted Codex configuration and whether the API-key environment variable is present.
- `start`: resolves the task, creates `.aai/`, initializes a campaign, optionally configures Codex, and writes `aai_start.json` plus startup runtime logs.
- `bootstrap`: packs and snapshots the current target solution as immutable baseline evidence.
- `prepare-child`: creates an isolated child workspace with `parent_solution/` and editable `workspace/solution/`.
- `run-codex-agent`: runs Codex CLI against the prepared child workspace and writes `codex_agent_run.json` plus runtime logs.
- `run-child-eval`: runs pack/local/modal evaluator scripts against an existing child workspace without archiving.
- `run-child-round`: evaluates, gates, archives, and writes `round_report.json`; use `--skip-prepare` after Codex edits.
- `summarize-campaign`: reads all child round reports and writes `campaign_summary.json` / `campaign_summary.md`.
- `update-campaign-memory`: appends campaign findings into `harness-ledger.md` and repeated failures into `TRAPS.md`.
- `select-parent`: picks the best archived baseline/variant for the next round.

For the full startup guide, runtime log layout, and complete command reference, see [`aai_harness/README.md`](./aai_harness/README.md).

From the repository root:

```bash
PYTHONPATH=agent-assisted python -m aai_harness.cli --help
```

## Evaluator scripts

AAI keeps `scripts/` because the harness still uses these as evaluator/packing backends:

- `scripts/pack_solution.py`
- `scripts/run_local.py`
- `scripts/run_modal_single.py`
- `scripts/run_modal_multiple_gpus.py`

Use them directly only for low-level debugging. Normal AAI usage should go through `python -m aai_harness.cli ...`.
