# AAI Full-Agent Reuse Guide

This document captures the working direction for building **AAI as agentic AI infrastructure** while reusing the useful parts of the `full-agent` / LoongFlow project. It is intended to guide the next generation of the AAI harness.

## Core thesis

AAI should not copy the kernel-op contest package as-is. AAI should reuse the **agent runtime architecture** behind full-agent:

```text
Reuse: PES runtime, worker abstraction, evaluator gate, database/checkpoint,
       trace schema, and Codex executor ideas.
Modify: kernel tasks, FlashInfer evaluator, latency/speedup metrics,
        CUDA/Triton prompts, and contest-specific trace contents.
```

The practical rule is:

```text
Keep the automatic-lab infrastructure.
Replace the fact that the historical lab happened to optimize kernels.
```

---

## 1. Content that should be reused from full-agent

### 1.1 BasePESRunner: generic agent launcher

`BasePESRunner` is worth reusing or re-implementing as AAI's generic runtime runner.

It is responsible for:

```text
1. parsing CLI arguments
2. loading YAML config
3. merging CLI overrides
4. validating the final config
5. setting up logging
6. creating PESAgent
7. registering planner / executor / summarizer workers
8. starting the async agent loop
```

For AAI, this should become a generic `AAIRuntimeRunner` or `BaseAgentRuntimeRunner` that loads campaign config, backend config, worker registrations, and starts a bounded phase run.

### 1.2 PESAgent: Plan-Execute-Summary main loop

`PESAgent` is the core to reuse.

Full-agent uses a loop like:

```text
Context
  -> Planner.run()
  -> Executor.run()
  -> Evaluator evaluates produced candidate
  -> Summary.run()
  -> Database update / checkpoint
```

For AAI this should become a generalized phase runtime:

```text
Phase context
  -> planner worker
  -> executor worker
  -> evaluator / validator worker
  -> summarizer worker
  -> memory/checkpoint update
```

The key idea is **PES as an inner phase engine**, not as the outer workflow owner.

### 1.3 Worker registration and backend plug-in mechanism

Full-agent registers planner, executor, and summarizer workers by name. This plug-in model should be retained.

AAI should generalize it to:

```text
planner_backend   = loongflow | codex | rule | human | future
executor_backend  = codex | loongflow | shell | repo_agent | browser | future
evaluator_backend = tests | policy | CI | human_review | deployment | future
summary_backend   = llm | rule | hybrid | future
```

The outer AAI workflow should select which runtime and worker set runs inside each phase.

### 1.4 EvolveDatabase: memory, parent selection, lineage, checkpoint

Full-agent's evolutionary database is not just a log. It stores candidate solutions, samples parents, tracks lineage, supports checkpointing/resume, and maintains diversity.

AAI should reuse the concept, but rename the domain objects:

```text
full-agent term       AAI infra term
---------------       ----------------
solution              candidate / artifact / attempt
parent_solution       parent candidate / parent artifact
best_solution         best candidate
score                 evaluation score / utility score
checkpoint            campaign or phase checkpoint
```

AAI should keep:

```text
sample_candidate()
add_candidate()
update_candidate()
memory_status()
save_checkpoint()
load_checkpoint()
get_parents_by_child_id()
get_children_by_parent_id()
get_best_candidates()
```

### 1.5 Evaluator interface and EvaluationResult schema

Full-agent's evaluator abstraction should be retained, but generalized.

Useful schema:

```text
status
summary
score
metrics
artifacts
```

AAI should extend status values to include infra outcomes:

```text
success
failed
incomplete
policy_violation
needs_review
timeout
framework_error
```

AAI metrics should not be hard-coded to latency/speedup. Metrics can include:

```text
test pass rate
policy compliance
deployment success
tool-call correctness
task completion quality
cost
runtime
diff risk
human review result
```

The full-agent pattern of running evaluation in a separate process with timeout and writing result/log files is worth retaining.

### 1.6 Trace schema and auditability

Full-agent trace layout is valuable as an audit pattern, not as kernel-specific content.

Historical structure:

```text
database/checkpoints/
  best_solution.json
  metadata.json
  solutions/

iteration/{K}/
  planner/
  executor/
  summarizer/

evaluator/eval_<hash>/
  llm_code_*.py
  evaluation_process.log
  result.json
```

AAI should normalize this into a backend-agnostic trace contract:

```text
trace/
├── manifest.json
├── planner/
├── executor/
├── evaluator/
├── summarizer/
├── database/
├── artifacts/
└── events.jsonl
```

The important property is that every phase can be audited: why the agent planned something, what it changed, how it was evaluated, why it was accepted or rejected, and how memory changed afterward.

### 1.7 Codex executor idea

Full-agent already contains the idea that Codex can be an executor backend or fallback inside a PES iteration. This should be reused conceptually.

AAI should adapt the trigger logic from kernel-specific conditions to infra conditions:

```text
Trigger Codex when:
- tests fail
- policy checks fail
- agent output is incomplete
- patch is too risky or too broad
- score is below threshold
- human requests refinement
- previous executor produced invalid artifacts
```

Codex should be a bounded executor inside a workspace. It should not own the global AAI workflow.

---

## 2. Full-agent content that is kernel-op-specific and must be changed

### 2.1 `math_agent` naming and task semantics

The historical entrypoint is shaped around math/code/kernel optimization. For AAI this should be renamed and generalized:

```text
old: agents/math_agent/math_evolve_agent.py
new: aai_runtime/agent_runner.py or aai_runtime/pes_runner.py
```

Do not keep `math_agent` as the core identity of AAI infra.

### 2.2 `initial_code`, `solution`, `best_solution`

These terms assume the object being optimized is code. AAI should use broader concepts:

```text
initial_artifact
candidate
parent_candidate
best_candidate
attempt
workspace_state
```

Kernel code can be one artifact type, but not the only type.

### 2.3 Kernel score metrics

Kernel-op metrics such as compile correctness, latency, speedup, and GPU benchmark score should not be core AAI metrics.

AAI should support domain-specific metrics as plugins, but the core should operate on generic `EvaluationResult` objects.

### 2.4 FlashInfer and Modal evaluator scripts

FlashInfer evaluator scripts, Modal GPU benchmark runners, and contest pack scripts should not be in AAI core. They can live as examples or historical references, but not as required dependencies.

AAI evaluator backends should include:

```text
pytest / unit tests
CI status
policy checks
static analysis
security checks
human review
deployment health
benchmark adapters
```

### 2.5 `run_<kernel_task>.sh` launchers

Scripts such as `run_gdn_decode.sh`, `run_dsa_sparse_attn.sh`, and `run_moe.sh` are task-specific launchers. AAI should use generic runtime profiles instead:

```text
runtime_profile.json
campaign.yaml
aai run --campaign <id>
aai runtime run --backend loongflow
```

### 2.6 CUDA/Triton prompts and task files

Do not keep kernel prompts in AAI core. The prompt system should be layered:

```text
system prompt: governance boundary and role
task prompt: user/campaign objective
runtime prompt: backend-specific instructions
evaluation prompt: evaluator-specific constraints
memory prompt: archive/summaries/traps
```

CUDA/Triton prompts should only be examples.

### 2.7 Kernel-specific Codex runner assumptions

The historical Codex runner contains kernel-specific concepts such as:

```text
ModelNew
min_speedup
eval_program_with_profile.py
initial_program.py
codex_seed.py
```

AAI's Codex adapter should instead use:

```text
workspace
task.md
allowed_paths
protected_paths
validation_command
test_command
output_contract
diff.patch
final_message.md
run_report.json
```

### 2.8 Kernel trace file names

Names such as `best_solution.py`, `llm_code_*.py`, and `solutions/` can be kept only as compatibility aliases. The normalized AAI trace should prefer:

```text
best_candidate/
candidate_artifacts/
executor_output/
evaluation_input/
evaluation_result.json
checkpoint.json
```

---

## 3. Direct reuse vs adapted reuse vs do not reuse

### Directly reuse or lightly modify

```text
BasePESRunner startup flow
PESAgent PES main loop
Worker registration mechanism
EvolveDatabase interface idea
EvaluationResult schema
Evaluator process isolation + timeout + logs
Checkpoint / resume mechanism
Trace-tree idea: iteration / evaluator / database
Codex executor/fallback concept
```

### Reuse after abstraction

```text
MathPESAgent
EvolvePlanAgent
EvolveExecuteAgent*
EvolveSummaryAgent
Workspace path helpers
Context schema
Database solution model
Finalizer
CodexRunner
```

These contain kernel/code-optimization semantics and must be renamed and generalized.

### Do not reuse in AAI core

```text
GDN / DSA / MoE kernels
FlashInfer benchmark scripts
Modal-specific evaluator as a required dependency
contest report PDFs
Full-agent-trace_* concrete historical traces
CUDA/Triton prompts
kernel-only skills
latency/speedup-specific gate logic
```

These can be examples or historical references, not core infrastructure.

---

## 4. Target AAI structure

A clean AAI infra branch should move toward:

```text
aai/
├── aai_harness/
│   ├── workflow.py
│   ├── campaign.py
│   ├── runtime_profile.py
│   ├── trace_contract.py
│   ├── validation.py
│   ├── archive.py
│   ├── memory.py
│   ├── proposal.py
│   └── cli.py
│
├── aai_runtime/
│   ├── pes_agent.py          # generalized from LoongFlow PESAgent
│   ├── base_runner.py        # generalized from BasePESRunner
│   ├── worker.py
│   ├── evaluator.py
│   ├── database.py
│   ├── checkpoint.py
│   └── context.py
│
├── aai_adapters/
│   ├── loongflow.py
│   ├── codex.py
│   ├── manual.py
│   └── ci.py
│
├── docs/
│   ├── AAI_INFRA_DESIGN.md
│   ├── TRACE_CONTRACT.md
│   └── MODE3_PROPOSALS.md
│
├── tests/
└── examples/
    ├── toy_code_agent/
    ├── toy_research_agent/
    └── toy_ci_fix_agent/
```

---

## 5. How LoongFlow should fit inside the user-designed AAI workflow

LoongFlow should be an **inner phase runtime**, not the outer workflow owner.

AAI owns the external workflow:

```text
需求解析 / 可行性判断
模式 0 bootstrap
阶段 1 bounded child optimization
阶段 2 Master Campaign archive / parent selection / memory
Mode 3 harness-change proposals
```

LoongFlow can run inside a phase, for example:

```text
AAI phase node: spawn child and run worker agent
  -> backend = loongflow
  -> LoongFlow runs planner/executor/evaluator/summarizer internally
  -> LoongFlow emits trace/evidence
  -> AAI imports and validates evidence
  -> AAI decides archive / reject / memory update / next phase
```

The outer AAI workflow can be handmade, graph-authored, or human-reviewed. This is not only allowed; it is the right division of responsibility.

LoongFlow should not decide the global campaign phase transitions. It should only provide execution evidence for a specific phase instance.

---

## 6. Final rule

```text
AAI = external workflow governance and evidence control plane.
LoongFlow = one possible inner runtime for a phase.
Codex = one possible bounded executor backend.
Human = allowed workflow author / reviewer / approval gate.
```
