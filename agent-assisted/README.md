# Agent-Assisted FlashInfer Contest Package

This directory is the agent-assisted reproducibility package for our MLSys
2026 FlashInfer AI Kernel Generation Contest submissions. It contains the
retained kernels, submission configs, benchmark artifacts, workflow scripts,
agent skills, and the agent-assisted technical report.

## Layout

```text
.
|-- report.pdf
|-- scripts/
|-- skills/
|-- aai_harness/
|-- AAI_HARNESS.md
|-- moe_fp8_block_scale_ds_routing_topk8_ng8_kg4_e32_h7168_i2048/
|-- gdn_decode_qk4_v8_d128_k_last/
|-- gdn_prefill_qk4_v8_d128_k_last/
|-- dsa_sparse_attention_h16_ckv512_kpe64_topk2048_ps64/
`-- dsa_topk_indexer_fp8_h64_d128_topk2048_ps64/
```

Each kernel directory contains:

- `config.toml`: FlashInfer submission metadata.
- `solution/`: Triton or CUDA source loaded by the evaluator.
- `artifacts/`: retained benchmark logs and summaries.
- `README.md`: per-kernel notes, entry point, candidate name, and retained
  result.

## Retained Kernels

| Track | Kernel | Retained result |
| --- | --- | --- |
| MoE FP8 | [Block-scale routing](./moe_fp8_block_scale_ds_routing_topk8_ng8_kg4_e32_h7168_i2048/)<br>`kernel.py::run` | 19/19 passed<br>0.289740 ms, three-repeat mean |
| Gated DeltaNet | [Decode QK4](./gdn_decode_qk4_v8_d128_k_last/)<br>`kernel.py::kernel_hybrid_dispatch` | 54/54 passed<br>0.006201 ms average |
| Gated DeltaNet | [Prefill QK4](./gdn_prefill_qk4_v8_d128_k_last/)<br>`kernel.py::kernel_prefill_hybrid` | 100/100 passed<br>0.051992 ms average |
| DeepSeek Sparse Attention | [Sparse attention](./dsa_sparse_attention_h16_ckv512_kpe64_topk2048_ps64/)<br>`kernel.py::run` | 23/23 passed<br>0.011128 ms average |
| DeepSeek Sparse Attention | [Top-k indexer](./dsa_topk_indexer_fp8_h64_d128_topk2048_ps64/)<br>`kernel.cu::kernel_cuda` | 128/128 passed<br>0.006893 ms average |

## Setup

```bash
conda create -n fi-bench python=3.12
conda activate fi-bench
pip install flashinfer-bench modal
modal setup
modal volume create flashinfer-trace
modal volume put flashinfer-trace /path/to/mlsys26-contest-trace/
```

The Modal scripts expect the official contest workloads to be available in the
`flashinfer-trace` volume mounted at `/data`.

## Pack a Solution

Run commands from this `agent-assisted/` directory:

```bash
python scripts/pack_solution.py \
  --config-path gdn_decode_qk4_v8_d128_k_last/config.toml \
  --output /tmp/gdn_decode.solution.json
```

## Evaluation

Use `--config-path` to select the kernel to evaluate. The scripts read the
definition, implementation language, entry point, and solution directory from
that `config.toml`.

For local evaluation on a machine with the dataset and a compatible CUDA GPU:

```bash
export FIB_DATASET_PATH=/path/to/mlsys26-contest
python scripts/run_local.py \
  --config-path dsa_topk_indexer_fp8_h64_d128_topk2048_ps64/config.toml
```

For Modal B200 single-workload evaluation:

```bash
python -m modal run scripts/run_modal_single.py \
  --workload-uuid <workload_uuid_or_index> \
  --config-path dsa_topk_indexer_fp8_h64_d128_topk2048_ps64/config.toml \
  --official --no-profile-torch --no-profile-ncu
```

For Modal B200 full-kernel evaluation:

```bash
export FIB_DATASET_PATH=/path/to/mlsys26-contest
python scripts/run_modal_multiple_gpus.py \
  --config-path dsa_topk_indexer_fp8_h64_d128_topk2048_ps64/config.toml \
  --workers 10 \
  --out-dir results/dsa_topk_indexer_fp8_h64_d128_topk2048_ps64
```

To retry only missing or failed workloads from an existing output directory:

```bash
python scripts/run_modal_multiple_gpus.py \
  --config-path dsa_topk_indexer_fp8_h64_d128_topk2048_ps64/config.toml \
  --workers 4 \
  --out-dir results/dsa_topk_indexer_fp8_h64_d128_topk2048_ps64 \
  --retry
```

## Agent Workflow Skills

The [skills](./skills/) directory contains the workflow instructions used for
optimization and submission handling:

| Skill | Purpose |
| --- | --- |
| [flashinfer-b200-contest-optimizer](./skills/flashinfer-b200-contest-optimizer/) | FlashInfer B200 contest loop: reference-first recon, shape-aware Modal benchmarking, NCU analysis, and promotion gates. |
| [flashinfer-submission-tagger](./skills/flashinfer-submission-tagger/) | Submission tag and `config.toml` topology validation helper. |

For broader repository context and the autonomous full-agent package, see the
top-level [README](../README.md).

## Agentic AI Harness Workflow

This fork adds an optional AAI harness layer under [`aai_harness/`](./aai_harness/) plus the design note [`AAI_HARNESS.md`](./AAI_HARNESS.md).

The layer wraps the existing `scripts/` evaluators instead of replacing them. It provides Codex-backed child-agent execution, isolated workspaces, detailed runtime logs, timestamp-versioned evidence, archive gates, Master Campaign state, variant/failed archival, campaign summaries, TRAPS / harness-ledger memory, and Mode 3 evidence-backed proposal review.

### Codex-backed quick start

Run from this directory:

```bash
export CODEX_API_KEY=<your OpenAI API key>

python -m aai_harness.cli configure-codex \
  --model gpt-5.5-codex \
  --api-key-env CODEX_API_KEY

python -m aai_harness.cli start \
  --config-path gdn_decode_qk4_v8_d128_k_last/config.toml \
  --campaign-id campaign-demo \
  --codex-model gpt-5.5-codex

python -m aai_harness.cli bootstrap \
  --config-path gdn_decode_qk4_v8_d128_k_last/config.toml \
  --version 20260707T173000+0900

python -m aai_harness.cli prepare-child \
  --campaign-id campaign-demo \
  --child-id child-0001 \
  --parent-id baseline \
  --config-path gdn_decode_qk4_v8_d128_k_last/config.toml

python -m aai_harness.cli run-codex-agent \
  --campaign-id campaign-demo \
  --child-id child-0001 \
  --objective "Optimize the candidate solution while preserving correctness and evidence requirements."

python -m aai_harness.cli run-child-round \
  --campaign-id campaign-demo \
  --child-id child-0001 \
  --parent-id baseline \
  --config-path gdn_decode_qk4_v8_d128_k_last/config.toml \
  --mode modal-full \
  --workers 10 \
  --kind variant \
  --skip-prepare

python -m aai_harness.cli summarize-campaign --campaign-id campaign-demo
python -m aai_harness.cli update-campaign-memory --campaign-id campaign-demo
python -m aai_harness.cli select-parent --definition gdn_decode_qk4_v8_d128_k_last
```

Important: after `run-codex-agent`, pass `--skip-prepare` to `run-child-round`; otherwise the child workspace is recreated and the Codex candidate can be overwritten.

### Command meanings

- `configure-codex`: records Codex model, binary, sandbox, timeout, and API-key environment variable name in `.aai/codex_config.json`; it does not store the API key.
- `codex-status`: prints redacted Codex configuration and whether the API-key environment variable is present.
- `start`: resolves the task, creates `.aai/`, initializes a campaign, optionally configures Codex, and writes `aai_start.json` plus startup runtime logs.
- `bootstrap`: packs and snapshots the current repository solution as immutable baseline evidence.
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

## License

This package is licensed under the [Apache License 2.0](../LICENSE).

## Citation

If this work is helpful, please cite the technical report:

```bibtex
@misc{shui2026harnessengineering,
  title        = {Harness Engineering for LLM-Driven GPU Kernel Generation},
  author       = {Yue Shui and Chenyu Ma and Hangfei Xu and Shengzhao Wen and Yanpeng Wang},
  year         = {2026},
  howpublished = {\url{https://github.com/syhya/mlsys26-flashinfer-contest}},
  note         = {Technical report for the MLSys 2026 FlashInfer AI Kernel Generation Contest}
}
```
