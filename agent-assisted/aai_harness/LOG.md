# AAI Harness Modification Log

## Version `20260707T160734+0900`

Timestamp timezone: Asia/Tokyo.

### Changes

- Added the initial `agent-assisted/aai_harness/` Python package.
- Added timestamp-versioned schemas for task specs, evidence records, metrics, artifact references, gate findings, and proposal reviews.
- Added Mode 0 bootstrap support that validates `config.toml`, packs the current solution through the existing `scripts/pack_solution.py`, snapshots config/source, and optionally runs local baseline evaluation.
- Added evaluator wrappers for existing Modal single-workload and multi-workload scripts without modifying those scripts.
- Added archive gates for correctness status, protected-path edits, hidden-eval/leaderboard patterns, hardcoded workload UUID patterns, and evidence schema presence.
- Added archive helpers for baseline, variant, failed-run manifests, `harness-ledger.md`, and `TRAPS.md` updates.
- Added Master Campaign initialization and narrow child prompt generation.
- Added Mode 3 `PROPOSALS.md` template and proposal review checks.
- Added CLI entrypoint: `python -m aai_harness.cli ...`.
- Added `agent-assisted/aai_harness/README.md` and `agent-assisted/AAI_HARNESS.md`.

### Notes

- Existing evaluator scripts were intentionally left unchanged in this version.
- All files were committed to branch `aai-harness-workflow` after GitHub connector write access was restored.
