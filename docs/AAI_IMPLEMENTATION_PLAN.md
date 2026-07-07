# AAI Implementation Plan

This document archives the current implementation plan for building AAI from the current `main` branch.

## Goal

Build **AAI as agentic AI infrastructure**, not as an agentic kernel-op benchmark package.

AAI is the outer workflow and governance layer. LoongFlow and Codex are runtime backends that can be called inside specific workflow phases.

```text
AAI = external workflow governance, artifact contracts, gates, archive, memory, Mode 3 review
LoongFlow = phase-local Plan/Execute/Evaluate/Summarize runtime
Codex = bounded executor backend inside a workspace
Human = workflow author, reviewer, and approval gate
```

## Boundary decision

LoongFlow may design and execute the workflow *inside a phase*.

LoongFlow must not own the global AAI workflow. The global workflow is authored and governed by AAI, and may be manually created from a diagram, YAML, JSON, or UI editor.

## Phased implementation

### Phase 0: archive design

- Keep `docs/AAI_FULL_AGENT_REUSE_GUIDE.md`.
- Add this implementation plan.
- Add `docs/AAI_WORKFLOW_CONTRACT.md` to translate the drawio workflow into an executable state/artifact contract.

### Phase 1: create AAI harness skeleton

Create:

```text
aai_harness/
  __init__.py
  schemas.py
  paths.py
  workflow.py
  cli.py
```

The first implementation should be dependency-light and should only implement the outer control plane.

### Phase 2: implement the external workflow state machine

Translate the workflow into states and transitions:

```text
request received
requirements parsed
bootstrap scoped / built / health checked / baseline evaluated
campaign ready
parent selected
round planned
child running
child evidence ready
prearchive checked
variant archived or failed archived
memory updated
proposal written / reviewed
completed
```

Every transition should be artifact-gated. A runtime may create evidence, but AAI validates and advances state.

### Phase 3: add runtime adapters

Add adapters only after the outer workflow contract exists:

```text
aai_adapters/
  loongflow.py
  codex.py
  manual.py
```

LoongFlow should be called by AAI as a phase runtime. It should return a trace/evidence bundle.

### Phase 4: normalize traces

Use a backend-neutral trace contract:

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

Map LoongFlow traces into the AAI trace contract instead of making AAI depend on LoongFlow's historical kernel trace layout.

### Phase 5: archive, memory, and Mode 3

Implement:

```text
archive_variant
archive_failed
update_memory
proposal_template
review_proposal
accept_proposal
apply_proposal
```

No runtime can directly modify workflow, archive, evaluator, scoring, gates, or long-term memory unless an accepted Mode 3 proposal authorizes that change.

### Phase 6: cleanup

Only after the AAI core and toy examples work, remove or move kernel-op-specific assets from the final AAI branch.

Do not keep these in AAI core:

```text
GDN / DSA / MoE kernels
FlashInfer benchmark scripts
Modal GPU benchmark as required dependency
contest report PDFs
concrete Full-agent-trace_* historical traces
CUDA/Triton prompts
latency/speedup-specific gate logic
```

These may remain as examples or historical references outside the core.
