# AAI Harness Modification Log

## Version `20260707T173000+0900`

Timestamp timezone: Asia/Tokyo.

### Changes

- Expanded `agent-assisted/aai_harness/README.md` into a full startup guide.
- Added a Codex-backed AAI quick start from API-key export through Codex execution, evaluation, archive, campaign summary, memory update, and parent selection.
- Added a complete command reference explaining `configure-codex`, `codex-status`, `start`, `bootstrap`, `prepare-child`, `write-codex-prompt`, `run-codex-agent`, `run-child-eval`, `run-child-round`, `diff-child`, `finalize-child`, `gate`, `archive`, `gate-archive`, `summarize-campaign`, `update-campaign-memory`, `select-parent`, `proposal-template`, and `review-proposal`.
- Added explicit warning that `run-child-round` must use `--skip-prepare` after `run-codex-agent`, otherwise a prepared workspace may be recreated and the Codex candidate can be overwritten.
- Expanded `agent-assisted/README.md` with a short Codex-backed quick start and a concise command glossary that links to the detailed AAI harness README.

### Notes

- This version is documentation-only. No runtime code was changed.
- The command flow now documents the safe Codex-backed path: configure, start, bootstrap, prepare child, run Codex, evaluate/archive with `--skip-prepare`, summarize, update memory, and select next parent.

## Version `20260707T172000+0900`

Timestamp timezone: Asia/Tokyo.

### Changes

- Added `runtime_logging.py` for detailed runtime traces:
  - append-only `runtime_trace.jsonl` event stream;
  - redacted `environment.json` platform/environment snapshots;
  - command start/end events with return codes and durations;
  - per-command stdout/stderr artifacts under `commands/`.
- Added `codex_adapter.py` for OpenAI Codex CLI support as the first AAI child-agent backend.
- Added `.aai/codex_config.json` configuration support via `configure-codex`.
- Added Codex-related CLI commands:
  - `configure-codex`;
  - `codex-status`;
  - `write-codex-prompt`;
  - `run-codex-agent`.
- Added `start.py` and `start` CLI command for initializing an AAI campaign and optionally configuring Codex in one step.
- `run-codex-agent` invokes Codex non-interactive mode, captures JSONL/stdout/stderr/final-message artifacts, and writes `codex_agent_run.json`.
- Updated `run-child-eval` to emit detailed runtime traces and redacted environment snapshots for pack/local/modal evaluator commands.
- Updated README and design plan documentation for Codex adapter setup and runtime debugging.

### Notes

- API keys are never written to config files or logs. AAI stores only the configured environment variable name, such as `CODEX_API_KEY`.
- The default adapter command is `codex exec --sandbox workspace-write --model <model> --json --ephemeral ...`; use `--command-template` if your installed Codex CLI version uses different flags.

## Version `20260707T171000+0900`

Timestamp timezone: Asia/Tokyo.

### Changes

- Added `memory.py` for Master Campaign long-term memory updates.
- Added `update-campaign-memory` CLI command.
- The command reads or creates `campaign_summary.json` and `campaign_summary.md`.
- Added `memory_update.json` report generation under each campaign directory.
- Added automatic appends to `archive/<definition>/harness-ledger.md` with compact campaign state, best child, and recommended next steps.
- Added automatic appends to `archive/<definition>/traps/TRAPS.md` for repeated gate failure codes and failed child statuses.
- Added `--min-failure-count` to control trap emission threshold.
- Added `--no-traps` for ledger-only memory updates.
- Updated CLI, README, and design plan documentation for campaign memory updates.

### Notes

- Memory updates are append-only and auditable through `memory_update.json`.
- If a campaign summary does not contain a definition, pass `--definition` explicitly.

## Version `20260707T170312+0900`

Timestamp timezone: Asia/Tokyo.

### Changes

- Added `summary.py` for campaign-level rollup over child `round_report.json` files.
- Added `summarize-campaign` CLI command.
- `summarize-campaign` writes:
  - `campaign_summary.json` for machine-readable campaign state;
  - `campaign_summary.md` for a human-readable campaign dashboard.
- Added summary counters for total children, total round reports, gate passes, archived variants, archived failures, archived baselines, missing round reports, status counts, mode counts, archive-kind counts, and repeated gate failure codes.
- Added best-child selection by metric among gated archived variants.
- Added recommended next steps based on campaign state, gate failure codes, and missing round reports.
- Updated README and design plan documentation for campaign summaries.

### Notes

- The summary command is read-only with respect to child evidence; it only writes campaign-level summary artifacts.
- The default metric is `avg_latency_ms`, but the CLI accepts `--metric` for other numeric evidence metrics.

## Version `20260707T165028+0900`

Timestamp timezone: Asia/Tokyo.

### Changes

- Added `round.py` for one-command child round orchestration.
- Added `run-child-round` CLI command.
- `run-child-round` executes: prepare child workspace, run selected evaluator, gate evidence, archive evidence, and write `round_report.json`.
- Added `ChildRoundReport` schema for recording requested archive kind, final archive kind, gate status, evidence path, diff path, archive manifest, and notes.
- Gate failures are archived as failed evidence when the requested archive kind is `variant`.
- Updated README and design plan documentation to make `run-child-round` the high-level workflow entry point while preserving lower-level commands for debugging.

### Notes

- `pack` mode remains a smoke test and normally archives as failed evidence when requested as a variant, because full benchmark evidence is required for promotion.
- `modal-full` is the intended mode for promotion-quality child round evidence.

## Version `20260707T164312+0900`

Timestamp timezone: Asia/Tokyo.

### Changes

- Added `child_eval.py` for running existing evaluator scripts against isolated child workspaces.
- Added `run-child-eval` CLI command with modes:
  - `pack`: run `scripts/pack_solution.py` against `workspace/config.toml` and `workspace/solution`;
  - `local`: run pack first, then `scripts/run_local.py` when `FIB_DATASET_PATH` is available;
  - `modal-full`: run pack first, then `scripts/run_modal_multiple_gpus.py` with child workspace paths and child output directory.
- Added `child_eval.json` report generation with command list, return codes, log paths, and artifact paths.
- Added automatic stdout/stderr capture under each child `logs/` directory.
- Connected evaluator output to `finalize_child_evidence`, so `run-child-eval` refreshes `diff.patch` and writes child `result.json` by default.
- Updated archive gates to reject incomplete benchmark evidence such as `NO_BENCHMARK_RESULT`, `UNKNOWN`, and skipped local runs before variant promotion.
- Updated CLI, README, and design plan documentation for the new child evaluation runner.

### Notes

- This version still does not merge or promote child candidates automatically; `gate-archive` remains an explicit separate step.
- The evaluator runner uses existing scripts as the source of truth and passes workspace paths explicitly, avoiding mutation of repository-level submitted solutions.

## Version `20260707T163714+0900`

Timestamp timezone: Asia/Tokyo.

### Changes

- Added `diffing.py` for git-like text diff capture between parent solution snapshots and child candidate workspaces.
- Added `workspace.py` for child workspace lifecycle management:
  - create `.aai/campaigns/<campaign_id>/children/<child_id>/`;
  - copy immutable parent solution into `parent_solution/`;
  - create mutable candidate solution under `workspace/solution/`;
  - write `child.json` metadata;
  - create placeholder `ITERATIONS.md`, `trajectory.json`, and `audit.json`;
  - finalize child `result.json` using the shared `EvidenceRecord` schema.
- Added `parent_selection.py` for simple latency-based parent selection over archived baselines and variants.
- Added CLI commands: `prepare-child`, `diff-child`, `finalize-child`, and `select-parent`.
- Updated `agent-assisted/aai_harness/README.md` with child workspace lifecycle usage and archive layout.
- Updated `agent-assisted/AAI_HARNESS.md` to mark child workspace and diff capture as implemented.

### Notes

- This version still does not automatically run an evaluator inside the child workspace. It prepares the workspace and evidence contract; existing evaluator scripts can be pointed at `workspace/config.toml` and `workspace/solution` explicitly.
- Parent selection is intentionally simple in this version: lowest available latency metric among non-failed archived candidates, with fallback to latest baseline.

## Version `20260707T160734+0900`

Timestamp timezone: Asia/Tokyo.

### Changes

- Added the initial `agent-assisted/aai_harness/` Python package.
- Added timestamp-versioned schemas for task specs, evidence records, metrics, artifact references, gate findings, and proposal reviews.
- Added Mode 0 bootstrap support that validates `config.toml`, packs the current solution through the existing `scripts/pack_solution.py`, snapshots config/source, and optionally runs local baseline evaluation.
- Added evaluator wrappers for existing Modal single-workload and multi-workload scripts without modifying those scripts.
- Added archive gates for correctness status, protected-path edits, eval-governance patterns, hardcoded workload patterns, and evidence schema presence.
- Added archive helpers for baseline, variant, failed-run manifests, `harness-ledger.md`, and `TRAPS.md` updates.
- Added Master Campaign initialization and narrow child prompt generation.
- Added Mode 3 `PROPOSALS.md` template and proposal review checks.
- Added CLI entrypoint: `python -m aai_harness.cli ...`.
- Added `agent-assisted/aai_harness/README.md` and `agent-assisted/AAI_HARNESS.md`.

### Notes

- Existing evaluator scripts were intentionally left unchanged in this version.
- All files were committed to branch `aai-harness-workflow` after GitHub connector write access was restored.
