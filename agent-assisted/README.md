# Agentic AI Infrastructure Harness Package

This directory contains the AAI harness package and the evaluator scripts that the harness can call.

The old retained-kernel directories, old agent workflow skills, historical report PDF, and full-agent trace package have been removed from this branch. AAI does not need to vendor those artifacts. Instead, AAI expects a target package to be supplied through a `config.toml` path such as:

```text
<definition>/config.toml
```

The target package should provide the solution directory and entry point expected by the existing evaluator scripts.

## Start here

For future agents taking over this project, read these first:

1. [`AAI_DEVELOPMENT_GUIDE.md`](./AAI_DEVELOPMENT_GUIDE.md): detailed development handoff, goals, current progress, risks, and next tasks.
2. [`AAI_HARNESS.md`](./AAI_HARNESS.md): design mapping from the user workflow to implementation modules.
3. [`AAI_FULL_AGENT_STYLE.md`](./AAI_FULL_AGENT_STYLE.md): how AAI mirrors the original full-agent / LoongFlow trace schema.
4. [`aai_harness/README.md`](./aai_harness/README.md): startup guide, command reference, and runtime layout.

## Layout

```text
.
|-- README.md
|-- AAI_DEVELOPMENT_GUIDE.md
|-- AAI_FULL_AGENT_STYLE.md
|-- AAI_HARNESS.md
|-- scripts/
`-- aai_harness/
```

Important paths:

- `aai_harness/`: AAI harness Python package, CLI, Codex adapter, runtime logging, archive gates, campaign summary, and memory update logic.
- `scripts/`: existing pack/local/Modal evaluator scripts that AAI uses for candidate evaluation.
- `AAI_HARNESS.md`: design note mapping the AAI workflow to the implementation modules.
- `AAI_FULL_AGENT_STYLE.md`: implementation note for the full-agent-style trace mirror.
- `AAI_DEVELOPMENT_GUIDE.md`: handoff document for future agents and developers.

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

python -m aai_harness.cli workflow-status \
  --campaign-id campaign-demo
```

AAI now uses a hard workflow state machine. Do not treat Codex as the global workflow controller; Codex is an executor backend for bounded child workspaces.

## Full-agent-style trace mirror

After one or more AAI rounds, mirror current artifacts into the original full-agent-style trace layout:

```bash
python -m aai_harness.full_agent_trace_cli sync \
  --campaign-id campaign-demo \
  --definition <definition> \
  --iteration 1 \
  --child-id child-0001
```

This writes under:

```text
.aai/campaigns/<campaign_id>/full_agent_trace/
```

It mirrors planner, executor, evaluator, summarizer, and checkpoint artifacts without restoring old historical full-agent traces.

## Command meanings

- `configure-codex`: records Codex model, binary, sandbox, timeout, and API-key environment variable name in `.aai/codex_config.json`; it does not store the API key.
- `codex-status`: prints redacted Codex configuration and whether the API-key environment variable is present.
- `start`: resolves the task, creates `.aai/`, initializes a campaign, configures Codex when requested, and writes `aai_start.json` plus `workflow.json`.
- `workflow-status`: prints the current hard workflow state and allowed next actions.
- `workflow-advance`: advances the workflow only along allowed transitions.
- `plan-round`: writes structured planner decisions as `plans/plan-<version>.json` and `.md`.
- `bootstrap`: packs and snapshots the current target solution as immutable baseline evidence.
- `prepare-child`: creates an isolated child workspace with `parent_solution/` and editable `workspace/solution/`.
- `run-codex-agent`: runs Codex CLI against the prepared child workspace and writes `codex_agent_run.json` plus runtime logs.
- `run-child-eval`: runs pack/local/modal evaluator scripts against an existing child workspace without archiving.
- `run-child-round`: evaluates, gates, archives, and writes `round_report.json`; use `--skip-prepare` after Codex edits.
- `summarize-campaign`: reads all child round reports and writes `campaign_summary.json` / `campaign_summary.md`.
- `update-campaign-memory`: appends campaign findings into `harness-ledger.md` and repeated failures into `TRAPS.md`.
- `admit-population`: admits a child round into population/checkpoint lineage memory.
- `population-status`: prints current population/checkpoint database state.
- `full_agent_trace_cli sync`: mirrors AAI artifacts into a full-agent-style trace tree.
- `select-parent`: picks the best archived baseline/variant for the next round.

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
